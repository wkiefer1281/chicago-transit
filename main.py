# main.py
from dotenv import load_dotenv
import os
from transit_modes.chicago_data_portal import fetch_cta_station_names
from transit_modes.cta_trains import fetch_train_locations
from transit_modes.cta_buses import fetch_all_bus_vehicles
from transit_modes.metra import fetch_metra_vehicle_positions, fetch_metra_stops
from utilities.utilities import upload_df

load_dotenv()

# Set Google credentials path for libraries like pandas_gbq
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

def collect_data():
    # metra
    metra_station_df = fetch_metra_stops()
    metra_train_df = fetch_metra_vehicle_positions()

    # trains
    cta_station_df = fetch_cta_station_names()
    cta_train_df = fetch_train_locations()

    # buses
    cta_bus_df = fetch_all_bus_vehicles()

    return {
        "cta_station_df": cta_station_df,
        "cta_train_df": cta_train_df,
        "cta_bus_df": cta_bus_df,
        "metra_station_df": metra_station_df,
        "metra_train_df": metra_train_df,
    }

def upload_to_bq(data_frames: dict):
    upload_df(data_frames["cta_station_df"], dataset="transit_data", table="cta_stations")
    upload_df(data_frames["metra_station_df"], dataset="transit_data", table="metra_stations")

    upload_df(data_frames["cta_train_df"], dataset="transit_data", table="cta_train_locations")
    upload_df(data_frames["cta_bus_df"], dataset="transit_data", table="cta_bus_locations")
    upload_df(data_frames["metra_train_df"], dataset="transit_data", table="metra_train_locations")

def display_data(data_frames: dict):
    for name, df in data_frames.items():
        print(f"{name} ({len(df)} rows)")
        print(df.head())

def resolve_mode() -> str:
    """
    Decide whether to display dataframes ('df') or upload to BigQuery ('bq').
    Set OUTPUT_MODE in the environment or adjust DEFAULT_MODE below.
    """
    DEFAULT_MODE = "df"
    env_mode = os.getenv("OUTPUT_MODE", "").lower()
    return env_mode if env_mode in {"df", "bq"} else DEFAULT_MODE

def main():
    data_frames = collect_data()

    mode = resolve_mode()

    if mode == "df":
        display_data(data_frames)
    else:
        upload_to_bq(data_frames)

if __name__ == "__main__":
    main()
