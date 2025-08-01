# main.py
import pandas as pd
from pandas_gbq import to_gbq
from google.cloud import bigquery
from transit_modes.trains import fetch_train_locations, parse_train_locations
from transit_modes.buses import fetch_all_bus_vehicles
from transit_modes.metra import fetch_metra_vehicle_positions

PROJECT_ID = "eternal-outlook-451201-d1"
DATASET = "transit_data"

def upload_df(df: pd.DataFrame, table: str):
    if not df.empty:
        full_table = f"{DATASET}.{table}"
        to_gbq(df, full_table, project_id=PROJECT_ID, if_exists="append")
        print(f"Uploaded {len(df)} rows to {full_table}")

def main():
    # trains
    xml_data = fetch_train_locations()
    train_df = parse_train_locations(xml_data)

    # buses
    bus_df = fetch_all_bus_vehicles()

    # # metra
    # vehicles_df = fetch_metra_vehicle_positions()
    # print("Live vehicles:", vehicles_df)

    # upload to BQ
    upload_df(train_df, "cta_train_locations")
    upload_df(bus_df, "cta_bus_locations")


if __name__ == "__main__":
    main()
