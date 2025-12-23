# chicago_data_portal.py
import os
from sodapy import Socrata
import pandas as pd

def fetch_cta_station_names():
    app_token = os.getenv("CHICAGO_APP_TOKEN")
    client = Socrata("data.cityofchicago.org", app_token)
    results = client.get("8pix-ypme", limit=2000)
    results_df = pd.DataFrame.from_records(results)

    # Keep only the relevant columns
    keep_columns = [
        'stop_id', 'direction_id', 'stop_name', 'station_name',
        'station_descriptive_name', 'map_id', 'ada', 'red', 'blue', 'g', 'brn',
        'p', 'pexp', 'y', 'pnk', 'o', 'location'
    ]
    results_df = results_df[[col for col in keep_columns if col in results_df.columns]]

    # Extract latitude and longitude from the 'location' dict
    if 'location' in results_df.columns:
        results_df["latitude"] = results_df["location"].apply(lambda loc: float(loc["latitude"]) if isinstance(loc, dict) else None)
        results_df["longitude"] = results_df["location"].apply(lambda loc: float(loc["longitude"]) if isinstance(loc, dict) else None)
        results_df = results_df.drop(columns=["location"])

    return results_df


