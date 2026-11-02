# chicago-transit

Pulls CTA (trains + buses) and Metra vehicle data into BigQuery on a schedule, keeps the full
history, and serves a live, animated map with delay analytics.

```
Cloud Scheduler (every 5 min) -> Cloud Run Job (main.py) -> BigQuery (project chicago-transit-513422)
                                                                 |
                                       FastAPI (server/) reads latest snapshot + history
                                                                 |
                                       React + Vega web app (web/) polls the API and animates vehicles
```

## BigQuery tables (dataset `transit_data`)

| Table | Load mode | Notes |
|---|---|---|
| `cta_train_locations`, `cta_bus_locations`, `metra_train_locations` | **append** | One batch of rows per run. Partitioned by day on `ingested_at`. |
| `cta_stations`, `metra_stations` | replace | Static reference data. |

Every run stamps all rows with the same `ingested_at` (UTC), so one run = one consistent snapshot.
The app shows `ingested_at = MAX(ingested_at)`; analytics over time group by `ingested_at`.
Metra's `positions` feed has no stop or status, and no trip for most trains, so the ETL fills `trip_id`, `route_id`,
`stop_id`, `current_stop_sequence` and `current_status` from its `tripupdates` feed (the next stop with a predicted time;
`INCOMING_AT` within 2 minutes, else `IN_TRANSIT_TO`). Anything Metra does report wins, and `current_status_source` says
which it was (`reported` / `derived` / null). Trains with no scheduled trip (yard moves) stay blank.
Metra never sends a delay either, so `delay_minutes` is the predicted arrival at that next stop minus its `stop_times.txt`
time, and `is_delayed` is true at 5 minutes or more (`DELAY_THRESHOLD_MIN`). Both are null when there is no prediction,
not false.
All timestamps are stored as UTC `TIMESTAMP`s (CTA's local-time strings are converted from `America/Chicago`).

Each source is fetched and loaded independently: if one API is down the others still load, and the
run exits non-zero so the failure shows up in Cloud Run.

## Local development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`uv sync`).

```bash
cp .env.example .env        # fill in keys; BQ_PROJECT_ID=chicago-transit-513422
OUTPUT_MODE=df uv run main.py   # fetch + print, touches nothing
uv run main.py                  # fetch + append to BigQuery
uv run pytest
```

Web app (two terminals; the Vite dev server proxies `/api` to the API):

```bash
uv run uvicorn server.app:app --reload     # API on :8000 (needs BQ_PROJECT_ID + GOOGLE_APPLICATION_CREDENTIALS)
cd web && npm install && npm run dev  # app on :5173
cd web && npm test                  # frame-interpolation tests
```

Configuration is read lazily from the environment, `.env`, and the optional
`CHICAGO_TRANSIT_SECRET_JSON` (real env vars win). See `.env.example`.

## Deploying the ETL (one-time setup, then `gcloud builds submit`)

```bash
P=chicago-transit-513422; R=us-central1
gcloud config set project $P
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com bigquery.googleapis.com

gcloud artifacts repositories create chicago-transit --repository-format=docker --location=$R

# ETL runtime identity: may load into BigQuery and read the secret
gcloud iam service-accounts create chicago-transit-etl
for role in roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding $P --member=serviceAccount:chicago-transit-etl@$P.iam.gserviceaccount.com --role=$role
done

# Scheduler identity: may run the job
gcloud iam service-accounts create scheduler-invoker
gcloud projects add-iam-policy-binding $P --member=serviceAccount:scheduler-invoker@$P.iam.gserviceaccount.com --role=roles/run.invoker

# One secret holding all API credentials as JSON
gcloud secrets create chicago-transit-secret --data-file=secret.json   # see payload below
gcloud secrets add-iam-policy-binding chicago-transit-secret \
  --member=serviceAccount:chicago-transit-etl@$P.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor

gcloud builds submit --config cloudbuild.yaml
```

Secret payload (`secret.json`, never commit it):
```json
{"CHICAGO_APP_TOKEN": "...", "CHICAGO_SECRET_TOKEN": "...", "CTA_TRAIN_API_KEY": "...",
 "CTA_BUS_API_KEY": "...", "METRA_API_TOKEN": "..."}
```

The schedule is the `_SCHEDULE` substitution in `cloudbuild.yaml` (default every 5 minutes).
The dataset is created automatically on the first run.
Note BigQuery allows 1,500 load jobs per table per day: running more often than once a minute exceeds that.

## Web app

`server/` is a small FastAPI service over the BigQuery tables (results cached for 60 s):

| Endpoint | Returns |
|---|---|
| `GET /api/summary` | Freshness, KPIs, % of trains delayed per line and the worst bus routes, from the latest snapshot |
| `GET /api/positions?minutes=60` | Every vehicle position per ETL snapshot (oldest first, max 180 min), used for animation |
| `GET /api/delay-history?window=24h` | Delayed vs. total trains per line over `6h`, `24h` or `7d` |
| `GET /api/meta` | Line colors and refresh interval |

`web/` is a Vite + React + TypeScript app that draws everything with [Vega-Lite](https://vega.github.io/vega-lite/)
(via `vega-embed`). The map is a Google Maps basemap (with its zoom buttons) under a transparent Vega layer that draws
the vehicles as a live dataset and follows the map's pan and zoom. The Maps JavaScript API key comes from the
`GOOGLE_MAPS_API_KEY` environment variable via `/api/meta` (use a browser key restricted by HTTP referrer). Without a
key, the map falls back to a Vega `geoshape` of Chicago's community areas and CTA track (`web/public/geo/`, simplified
from the City of Chicago data portal), which doesn't show Metra's suburbs or zoom.

The ETL only records a snapshot every few minutes, so the motion is interpolated: in **Live** mode vehicles glide to
their new positions whenever a refresh lands, and **Replay** plays back the last 30 min to 3 h at 30-300x, with a
scrubber. Vehicles are matched across snapshots by run number (trains) or vehicle id (buses, Metra) and only glide
between snapshots less than 15 minutes apart. Animation honors `prefers-reduced-motion`.

In production one container serves both: `Dockerfile.web` builds the frontend and runs `uvicorn server.app:app`,
which also serves `web/dist`. The service account needs `roles/bigquery.dataViewer` and `roles/bigquery.jobUser`.

```bash
docker build -f Dockerfile.web -t us-central1-docker.pkg.dev/$P/chicago-transit/web .
docker push us-central1-docker.pkg.dev/$P/chicago-transit/web
gcloud iam service-accounts create chicago-transit-web   # once
for role in roles/bigquery.dataViewer roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding $P --member=serviceAccount:chicago-transit-web@$P.iam.gserviceaccount.com --role=$role
done
gcloud run deploy chicago-transit-web --region=$R --image=us-central1-docker.pkg.dev/$P/chicago-transit/web \
  --service-account=chicago-transit-web@$P.iam.gserviceaccount.com --set-env-vars=BQ_PROJECT_ID=$P,GOOGLE_MAPS_API_KEY=$MAPS_KEY \
  --max-instances=3 --no-allow-unauthenticated
```

The service is private by default (open it locally with `gcloud run services proxy chicago-transit-web --region=$R`).
To make it public, keep `--max-instances` as a cost cap and allow all callers:

```bash
gcloud run services add-iam-policy-binding chicago-transit-web --region=$R \
  --member=allUsers --role=roles/run.invoker
```

The API warns if the newest data is more than 15 minutes old. `REFRESH_MS` (default 60000) sets how often the browser polls.
