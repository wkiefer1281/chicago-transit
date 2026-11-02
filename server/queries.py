# server/queries.py
from functools import lru_cache

import pandas as pd
from google.cloud import bigquery

from backend.config import bq_dataset, bq_project, require_env
from server.cache import ttl_cache

# How far back we look for the latest snapshot. Keeps the partition scan tiny while
# tolerating the ETL being down for a while.
SNAPSHOT_LOOKBACK_DAYS = 2


@lru_cache(maxsize=1)
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=require_env("BQ_PROJECT_ID"))


def _table(name: str) -> str:
    return f"`{bq_project()}.{bq_dataset()}.{name}`"


def _latest_snapshot(table: str, columns: str, extra_where: str = "") -> str:
    """SQL for the rows written by the most recent ETL run of `table`."""
    return f"""
    SELECT {columns}, ingested_at
    FROM {_table(table)}
    WHERE ingested_at = (
      SELECT MAX(ingested_at) FROM {_table(table)}
      WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {SNAPSHOT_LOOKBACK_DAYS} DAY)
    )
    AND ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {SNAPSHOT_LOOKBACK_DAYS} DAY)
    {extra_where}
    """


def _query(sql: str, params: list | None = None) -> pd.DataFrame:
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    return get_bq_client().query(sql, job_config=job_config).to_dataframe()


@ttl_cache(60)
def load_cta_trains() -> pd.DataFrame:
    return _query(_latest_snapshot(
        "cta_train_locations",
        """run_number, route, next_station_name, destination_station_name, is_delayed,
           predicted_time, arrival_time, latitude AS lat, longitude AS lon""",
        "AND latitude IS NOT NULL AND longitude IS NOT NULL",
    ))


@ttl_cache(60)
def load_cta_buses() -> pd.DataFrame:
    return _query(_latest_snapshot(
        "cta_bus_locations",
        "route, route_name, destination, is_delayed, speed_mph, vehicle_id, timestamp, lat, lon",
        "AND lat IS NOT NULL AND lon IS NOT NULL",
    ))


@ttl_cache(60)
def load_metra() -> pd.DataFrame:
    return _query(_latest_snapshot(
        "metra_train_locations",
        """route_id, route_short_name, trip_headsign, vehicle_id, vehicle_label,
           current_status, is_delayed, delay_minutes, timestamp, latitude AS lat, longitude AS lon""",
        "AND latitude IS NOT NULL AND longitude IS NOT NULL",
    ))


# mode -> (table, columns). Every mode is aliased to the same id/route/lat/lon/... shape
# so the history of all three can be fetched, stacked and replayed the same way.
_POSITION_QUERIES = {
    "trains": (
        "cta_train_locations",
        """CONCAT(route, '|', run_number) AS id, route, destination_station_name AS destination,
           next_station_name AS next_stop, is_delayed, latitude AS lat, longitude AS lon""",
        "latitude IS NOT NULL AND longitude IS NOT NULL AND run_number IS NOT NULL",
    ),
    "buses": (
        "cta_bus_locations",
        """vehicle_id AS id, route, destination, CAST(speed_mph AS INT64) AS speed_mph,
           is_delayed, lat, lon""",
        "lat IS NOT NULL AND lon IS NOT NULL AND vehicle_id IS NOT NULL",
    ),
    "metra": (
        "metra_train_locations",
        """vehicle_id AS id, COALESCE(NULLIF(route_short_name, ''), NULLIF(route_id, ''), 'Metra') AS route,
           trip_headsign AS destination, COALESCE(vehicle_label, vehicle_id) AS label,
           is_delayed, delay_minutes, latitude AS lat, longitude AS lon""",
        "latitude IS NOT NULL AND longitude IS NOT NULL AND vehicle_id IS NOT NULL",
    ),
}


@ttl_cache(60)
def load_positions(mode: str, minutes: int) -> pd.DataFrame:
    """Every vehicle position of `mode` from the last `minutes`, one row per run x vehicle."""
    table, columns, where = _POSITION_QUERIES[mode]
    sql = f"""
    SELECT {columns}, ingested_at
    FROM {_table(table)}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @minutes MINUTE)
      AND {where}
    ORDER BY ingested_at
    """
    return _query(sql, [bigquery.ScalarQueryParameter("minutes", "INT64", minutes)])


@ttl_cache(300)
def load_train_delay_history(hours: int, bucket_minutes: int) -> pd.DataFrame:
    """Delayed vs total trains per line per time bucket (one row per run x line, re-bucketed)."""
    sql = f"""
    SELECT
      TIMESTAMP_SECONDS(@bucket_s * DIV(UNIX_SECONDS(ingested_at), @bucket_s)) AS bucket,
      route,
      COUNTIF(is_delayed) AS delayed,
      COUNT(*) AS total,
      COUNT(DISTINCT ingested_at) AS snapshots
    FROM {_table("cta_train_locations")}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
    GROUP BY bucket, route
    ORDER BY bucket
    """
    return _query(sql, [
        bigquery.ScalarQueryParameter("hours", "INT64", hours),
        bigquery.ScalarQueryParameter("bucket_s", "INT64", bucket_minutes * 60),
    ])
