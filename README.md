# chicago-transit

Pipeline to pull CTA (trains + buses) and Metra data into BigQuery plus a small frontend to visualize it on a map.

## Prereqs
- Python 3.12+
- BigQuery project + dataset (`transit_data` by default)
- Environment variables: see `.env.example` (not provided here). Required: `CTA_TRAIN_API_KEY`, `CTA_BUS_API_KEY`, `METRA_API_TOKEN`, `CHICAGO_APP_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`, `BQ_PROJECT_ID`, optional `BQ_DATASET` (defaults to `transit_data`), `OUTPUT_MODE`.

## Secrets (Cloud Run job)
When running the scheduled Cloud Run job, set a single Secret Manager secret as a JSON payload and map it to `CHICAGO_TRANSIT_SECRET_JSON`.
Example payload:
```json
{
  "CHICAGO_APP_TOKEN": "abc",
  "CHICAGO_SECRET_TOKEN": "def",
  "CTA_TRAIN_API_KEY": "ghi",
  "CTA_BUS_API_KEY": "jkl",
  "METRA_API_TOKEN": "mno"
}
```
Local development uses `.env` instead; `CHICAGO_TRANSIT_SECRET_JSON` is optional locally.

## ETL
Populate the tables:
```bash
python main.py  # uses OUTPUT_MODE or defaults to uploading to BigQuery
```

## Streamlit (hostable)
Live map + simple analytics from BigQuery (in `frontend/app.py`):
```bash
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
```
Environment: `GOOGLE_APPLICATION_CREDENTIALS`, `BQ_PROJECT_ID`, optional `BQ_DATASET`, `STREAMLIT_REFRESH_MS` (default 15000), `STREAMLIT_ROW_LIMIT` (default 1200).
This auto-refreshes the page on a timer; adjust `STREAMLIT_REFRESH_MS` to tune polling. Use sidebar toggles to show/hide CTA trains, buses, and Metra layers. Metrics summarize counts and delayed percentages per route.
