# utilities/utilities.py
import os
import pandas as pd
from pandas_gbq import to_gbq
from dotenv import load_dotenv
from typing import Dict

load_dotenv()

PROJECT_ID = os.getenv("BQ_PROJECT_ID")
DATASET = "transit_data"
TABLES: Dict[str, str] = {
    "cta_station_df": "cta_stations",
    "cta_train_df": "cta_train_locations",
    "cta_bus_df": "cta_bus_locations",
    "metra_station_df": "metra_stations",
    "metra_train_df": "metra_train_locations",
}


def upload_df(df: pd.DataFrame, dataset: str, table: str):
    if not df.empty:
        full_table = f"{dataset}.{table}"
        to_gbq(df, full_table, project_id=PROJECT_ID, if_exists="replace")
        print(f"Uploaded {len(df)} rows to {full_table}")


def display_data(data_frames: dict):
    for name, df in data_frames.items():
        print(f"{name} ({len(df)} rows)")
        print(df.head())


def upload_data(data_frames: dict, dataset: str = DATASET):
    for key, table in TABLES.items():
        upload_df(data_frames[key], dataset=dataset, table=table)
