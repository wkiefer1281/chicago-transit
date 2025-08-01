# metra.py
import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

METRA_API_KEY = os.getenv("METRA_API_KEY")

BASE_URL = "https://gtfsapi.metrarail.com/gtfs"

def fetch_metra_routes() -> pd.DataFrame:
    headers = {"x-api-key": METRA_API_KEY}
    resp = requests.get(f"{BASE_URL}/schedule/routes", headers=headers)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())

def fetch_metra_vehicle_positions() -> pd.DataFrame:
    headers = {"x-api-key": METRA_API_KEY}
    resp = requests.get(f"{BASE_URL}/positions", headers=headers)
    resp.raise_for_status()
    data = resp.json().get("entity", [])
    records = []

    for entity in data:
        vehicle = entity.get("vehicle", {})
        ts = vehicle.get("timestamp")
        records.append({
            "id": entity.get("id"),
            "trip_id": vehicle.get("trip", {}).get("trip_id"),
            "route_id": vehicle.get("trip", {}).get("route_id"),
            "timestamp": datetime.fromtimestamp(ts).astimezone() if ts else None,
            "lat": vehicle.get("position", {}).get("latitude"),
            "lon": vehicle.get("position", {}).get("longitude"),
            "speed": vehicle.get("position", {}).get("speed"),
            "bearing": vehicle.get("position", {}).get("bearing"),
        })

    return pd.DataFrame(records)
