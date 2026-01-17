# frontend/bq_queries.py
import os
from typing import Optional

import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

PROJECT_ID = os.getenv("BQ_PROJECT_ID")
DATASET = os.getenv("BQ_DATASET", "transit_data")
DEFAULT_LIMIT = int(os.getenv("STREAMLIT_ROW_LIMIT", "1200"))


@st.cache_resource
def get_bq_client():
    if not PROJECT_ID:
        raise RuntimeError("BQ_PROJECT_ID is required to query BigQuery.")
    return bigquery.Client(project=PROJECT_ID)


def _table_ref(name: str) -> str:
    return f"`{PROJECT_ID}.{DATASET}.{name}`"


def _boolean_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"1", "true", "t", "yes", "y"})


@st.cache_data(ttl=20)
def load_cta_trains(limit: Optional[int] = None) -> pd.DataFrame:
    limit = limit or DEFAULT_LIMIT
    sql = f"""
    SELECT
      run_number,
      route,
      next_station_name,
      destination_station_name,
      is_delayed,
      predicted_time,
      arrival_time,
      CAST(latitude AS FLOAT64) AS lat,
      CAST(longitude AS FLOAT64) AS lon
    FROM {_table_ref("cta_train_locations")}
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    LIMIT {limit}
    """
    df = get_bq_client().query(sql).to_dataframe()
    if df.empty:
        return df
    df["is_delayed"] = _boolean_series(df["is_delayed"])
    return df


@st.cache_data(ttl=20)
def load_cta_buses(limit: Optional[int] = None) -> pd.DataFrame:
    limit = limit or DEFAULT_LIMIT
    sql = f"""
    SELECT
      route,
      destination,
      is_delayed,
      speed_mph,
      vehicle_id,
      timestamp,
      CAST(lat AS FLOAT64) AS lat,
      CAST(lon AS FLOAT64) AS lon
    FROM {_table_ref("cta_bus_locations")}
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    LIMIT {limit}
    """
    df = get_bq_client().query(sql).to_dataframe()
    if df.empty:
        return df
    df["is_delayed"] = _boolean_series(df["is_delayed"])
    return df


@st.cache_data(ttl=20)
def load_metra(limit: Optional[int] = None) -> pd.DataFrame:
    limit = limit or DEFAULT_LIMIT
    sql = f"""
    SELECT
      route_short_name,
      route_id,
      stop_name,
      vehicle_id,
      vehicle_label,
      current_status,
      timestamp,
      CAST(latitude AS FLOAT64) AS lat,
      CAST(longitude AS FLOAT64) AS lon
    FROM {_table_ref("metra_train_locations")}
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    LIMIT {limit}
    """
    return get_bq_client().query(sql).to_dataframe()
