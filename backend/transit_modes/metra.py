# metra.py

import io
import logging
import zipfile
from datetime import datetime
from functools import lru_cache

import pandas as pd
import requests
from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2

from backend.config import require_env
from backend.utilities import http
from backend.utilities.timeutils import CHICAGO_TZ

# Constants
REALTIME_BASE_URL = "https://gtfspublic.metrarr.com/gtfs/public"
STATIC_GTFS_URL = f"{REALTIME_BASE_URL}/schedule.zip"
REQUEST_TIMEOUT = 60

log = logging.getLogger(__name__)

# VehiclePosition.VehicleStopStatus
INCOMING_AT = gtfs_realtime_pb2.VehiclePosition.INCOMING_AT
IN_TRANSIT_TO = gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO
# A train predicted to reach its next stop within this long counts as arriving.
INCOMING_WITHIN_S = 120
# Predicted this many minutes behind the timetable at its next stop counts as delayed.
DELAY_THRESHOLD_MIN = 5


def _headers() -> dict:
    return {"Authorization": f"Bearer {require_env('METRA_API_TOKEN')}"}


# ============================
# Static GTFS Schedule Functions
# ============================

@lru_cache(maxsize=1)
def _download_gtfs_static() -> bytes:
    """Download schedule.zip once per process; it is shared by every static lookup."""
    return http.get(STATIC_GTFS_URL, headers=_headers(), timeout=REQUEST_TIMEOUT).content


def _load_gtfs_static_file(filename: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(_download_gtfs_static())) as z:
        with z.open(filename) as f:
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip()
            # Metra pads some values (' SWS_SW812_V2_AA', '  AURORA'), which breaks every join on them.
            for column in df.select_dtypes(include="object"):
                df[column] = df[column].str.strip()
            return df


def fetch_metra_stops() -> pd.DataFrame:
    df = _load_gtfs_static_file("stops.txt")

    df["zone_id"] = pd.to_numeric(df["zone_id"], errors="coerce")
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df["wheelchair_boarding"] = df["wheelchair_boarding"].astype("Int64")
    return df

def fetch_metra_routes() -> pd.DataFrame:
    return _load_gtfs_static_file("routes.txt")

def fetch_metra_trips() -> pd.DataFrame:
    return _load_gtfs_static_file("trips.txt")

def fetch_metra_stop_times() -> pd.DataFrame:
    return _load_gtfs_static_file("stop_times.txt")


# ============================
# Realtime GTFS Functions
# ============================

def _parse_realtime_feed(feed_name: str) -> gtfs_realtime_pb2.FeedMessage:
    url = f"{REALTIME_BASE_URL}/{feed_name}"
    response = http.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed

def _scheduled_seconds(stop_times: pd.DataFrame) -> pd.Series:
    """Timetable arrival at each (trip_id, stop_id), in seconds after the service day's start.

    GTFS times can pass 24:00:00 for trips that run past midnight, so they are parsed by hand.
    """
    parts = stop_times["arrival_time"].str.split(":", expand=True).apply(pd.to_numeric, errors="coerce")
    seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
    seconds.index = pd.MultiIndex.from_frame(stop_times[["trip_id", "stop_id"]])
    return seconds[~seconds.index.duplicated()].dropna()


def _service_day_start(start_date: str) -> float | None:
    """Epoch seconds GTFS times count from: noon of the service day minus 12 hours (right across DST)."""
    try:
        noon = datetime.strptime(start_date, "%Y%m%d").replace(hour=12, tzinfo=CHICAGO_TZ)
    except ValueError:
        return None
    return noon.timestamp() - 12 * 3600


def _delay_minutes(trip: gtfs_realtime_pb2.TripDescriptor, stop_id: str, predicted: int, schedule: pd.Series) -> float | None:
    day_start = _service_day_start(trip.start_date)
    scheduled = schedule.get((trip.trip_id, stop_id))
    if day_start is None or scheduled is None:
        return None
    return round((predicted - (day_start + scheduled)) / 60, 1)


def _next_stop_updates(feed: gtfs_realtime_pb2.FeedMessage, schedule: pd.Series | None = None) -> pd.DataFrame:
    """One row per vehicle: its trip and the next stop it is predicted to reach.

    Metra never sends a delay, so with the timetable (`schedule`) the row also says how far
    the prediction is behind it.

    Metra's positions feed carries no stop or status, but its trip updates list each running
    train's upcoming stops with predicted times, which is enough to say where it is headed.
    """
    now = feed.header.timestamp
    rows = []
    for entity in feed.entity:
        update = entity.trip_update
        vehicle_id = update.vehicle.id
        if not vehicle_id:
            continue
        upcoming = []
        for stu in update.stop_time_update:
            event = stu.arrival if stu.arrival.HasField("time") else stu.departure
            if event.HasField("time") and event.time >= now:
                upcoming.append((event.time, stu))
        if not upcoming:
            continue
        eta, stu = min(upcoming, key=lambda item: item[0])
        rows.append({
            "vehicle_id": vehicle_id,
            "update_trip_id": update.trip.trip_id,
            "update_route_id": update.trip.route_id,
            "update_start_time": update.trip.start_time,
            "update_start_date": update.trip.start_date,
            "update_stop_id": stu.stop_id,
            "update_stop_sequence": stu.stop_sequence if stu.HasField("stop_sequence") else None,
            "eta_seconds": eta - now,
            "update_delay_minutes": None if schedule is None else _delay_minutes(update.trip, stu.stop_id, eta, schedule),
        })
    columns = [
        "vehicle_id", "update_trip_id", "update_route_id", "update_start_time", "update_start_date",
        "update_stop_id", "update_stop_sequence", "eta_seconds", "update_delay_minutes",
    ]
    return pd.DataFrame(rows, columns=columns).drop_duplicates("vehicle_id")


def _fill_blank(df: pd.DataFrame, column: str, fallback: str) -> None:
    """Replace blank strings in `column` with `fallback`'s value (blank where that is missing too)."""
    blank = df[column].isna() | (df[column] == "")
    df[column] = df[column].where(~blank, df[fallback]).fillna("")


def _derive_stops(df: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    """Fill what the positions feed leaves blank (trip, route, current stop, status) from trip updates.

    Anything Metra does report is kept as is. `current_status_source` says which it was.
    """
    df = df.merge(updates, how="left", on="vehicle_id")

    for column in ("trip_id", "route_id", "start_time", "start_date"):
        _fill_blank(df, column, f"update_{column}")

    reported_status = df["current_status"].notna()
    # Derive the stop only for vehicles that report none, and only when an update exists for it.
    derive = (df["stop_id"] == "") & df["update_stop_id"].fillna("").ne("")
    df["stop_id"] = df["stop_id"].where(~derive, df["update_stop_id"])
    df["current_stop_sequence"] = df["current_stop_sequence"].where(~derive, df["update_stop_sequence"])

    derived_status = (~reported_status) & derive
    status = df["eta_seconds"].le(INCOMING_WITHIN_S).map({True: INCOMING_AT, False: IN_TRANSIT_TO})
    df["current_status"] = df["current_status"].where(~derived_status, status)
    df["current_status_source"] = pd.Series(pd.NA, index=df.index, dtype="string").mask(reported_status, "reported")
    df["current_status_source"] = df["current_status_source"].mask(derived_status, "derived")

    df["current_status"] = df["current_status"].astype("Int64")
    df["current_stop_sequence"] = pd.to_numeric(df["current_stop_sequence"]).astype("Int64")

    # Unknown (no prediction, or none that matches the timetable) stays null rather than "on time".
    df["delay_minutes"] = pd.to_numeric(df["update_delay_minutes"])
    df["is_delayed"] = (df["delay_minutes"] >= DELAY_THRESHOLD_MIN).astype("boolean").mask(df["delay_minutes"].isna())
    return df.drop(columns=[c for c in df.columns if c.startswith("update_") or c == "eta_seconds"])


def fetch_metra_vehicle_positions() -> pd.DataFrame:
    """Fetch realtime vehicle positions and enrich with static stop, route, and trip metadata."""
    feed = _parse_realtime_feed("positions")

    # ----------------------------
    # 1. Parse vehicle position feed
    # ----------------------------
    records = []
    for entity in feed.entity:
        vehicle = entity.vehicle
        pos = vehicle.position
        trip = vehicle.trip
        veh = vehicle.vehicle

        records.append({
            "entity_id": entity.id,
            "vehicle_id": veh.id,
            "vehicle_label": veh.label,
            "trip_id": trip.trip_id,
            "route_id": trip.route_id,
            "start_time": trip.start_time,
            "start_date": trip.start_date,
            "latitude": pos.latitude,
            "longitude": pos.longitude,
            "bearing": pos.bearing,
            "current_status": vehicle.current_status if vehicle.HasField("current_status") else None,
            "stop_id": vehicle.stop_id,
            "current_stop_sequence": vehicle.current_stop_sequence if vehicle.HasField("current_stop_sequence") else None,
            "timestamp": datetime.fromtimestamp(vehicle.timestamp, tz=CHICAGO_TZ) if vehicle.timestamp else None,
        })

    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["current_status"] = df["current_status"].astype("Int64")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Metra's positions leave out the stop, status and (for most trains) the trip, so fill them
    # from trip updates. If that feed is down, the positions are still worth keeping.
    try:
        updates = _next_stop_updates(fetch_metra_trip_updates(), _scheduled_seconds(fetch_metra_stop_times()))
    except (requests.RequestException, DecodeError):
        log.warning("Metra trip updates unavailable; leaving stop and status blank.", exc_info=True)
        updates = _next_stop_updates(gtfs_realtime_pb2.FeedMessage())
    df = _derive_stops(df, updates)

    # ----------------------------
    # 2. Join Static GTFS Metadata
    # ----------------------------
    stops_df = fetch_metra_stops()
    routes_df = fetch_metra_routes()
    trips_df = fetch_metra_trips()

    # Clean up before merge
    stops_df = stops_df[["stop_id", "stop_name", "stop_desc", "stop_lat", "stop_lon", "zone_id"]]
    routes_df = routes_df[["route_id", "route_short_name", "route_long_name", "route_type"]]
    trips_df = trips_df[["trip_id", "service_id", "trip_headsign", "direction_id"]]

    # Join static metadata
    df = df.merge(stops_df, how="left", on="stop_id")
    df = df.merge(routes_df, how="left", on="route_id")
    df = df.merge(trips_df, how="left", on="trip_id")

    # ----------------------------
    # 3. Combine datetime fields
    # ----------------------------
    # The feed often leaves these blank; coerce to NaT but keep a tz-aware UTC dtype
    # so the BigQuery column is always TIMESTAMP.
    df["start_datetime"] = (
        pd.to_datetime(df["start_date"] + " " + df["start_time"], format="%Y%m%d %H:%M:%S", errors="coerce")
        .dt.tz_localize(CHICAGO_TZ, ambiguous="NaT", nonexistent="NaT")
        .dt.tz_convert("UTC")
    )

    df.drop(columns=["start_time", "start_date"], inplace=True, errors="ignore")

    return df


def fetch_metra_trip_updates() -> gtfs_realtime_pb2.FeedMessage:
    return _parse_realtime_feed("tripupdates")

def fetch_metra_alerts() -> gtfs_realtime_pb2.FeedMessage:
    return _parse_realtime_feed("alerts")


