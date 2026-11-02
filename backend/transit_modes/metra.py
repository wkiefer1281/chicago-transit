# metra.py

import io
import zipfile
from datetime import datetime
from functools import lru_cache

import pandas as pd
from google.transit import gtfs_realtime_pb2

from backend.config import require_env
from backend.utilities import http
from backend.utilities.timeutils import CHICAGO_TZ

# Constants
REALTIME_BASE_URL = "https://gtfspublic.metrarr.com/gtfs/public"
STATIC_GTFS_URL = f"{REALTIME_BASE_URL}/schedule.zip"
REQUEST_TIMEOUT = 60


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
            "current_stop_sequence": vehicle.current_stop_sequence,
            "timestamp": datetime.fromtimestamp(vehicle.timestamp, tz=CHICAGO_TZ) if vehicle.timestamp else None,
        })

    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["current_status"] = df["current_status"].astype("Int64")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

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


