# cta_bus.py
import requests
import pandas as pd
from datetime import datetime
from itertools import islice
from typing import Generator
from dotenv import load_dotenv
import os

BASE_URL = "https://www.ctabustracker.com/bustime/api/v3"

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys from .env file
cta_bus_api_key = os.getenv('CTA_BUS_API_KEY')

# Helper function to convert time string to datetime in the format "YYYYMMDD HH:MM:SS"
def convert_to_datetime(t: str) -> datetime | None:
    for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d %H:%M"):
        try:
            dt = datetime.strptime(t, fmt)
            return dt.astimezone()  # Converts to system local timezone
        except (ValueError, TypeError):
            continue
    return None

def fetch_bus_routes() -> pd.DataFrame:

    url = f"{BASE_URL}/getroutes"
    params = {
        "key": cta_bus_api_key,
        "format": "json"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    routes = response.json().get("bustime-response", {}).get("routes", [])
    if not routes:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "route_id": r["rt"],
            "route_name": r["rtnm"],
            "route_color": r["rtclr"],
            "route_display": r["rtdd"]
        }
        for r in routes
    ])

def fetch_bus_locations(routes: list[str] = None, time_resolution: str = "s") -> pd.DataFrame:
    """Fetch current vehicle positions."""

    url = f"{BASE_URL}/getvehicles"
    params = {
        "key": cta_bus_api_key,
        "format": "json",
        "tmres": time_resolution  # “s” for second resolution
    }
    if routes:
        params["rt"] = ",".join(routes[:10])  # max 10 allowed

    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json().get("bustime-response", {})

    if "vehicle" not in data:
        return pd.DataFrame()

    vehicles = data["vehicle"]
    records = []

    for v in vehicles:
        records.append({
            "vehicle_id": v.get("vid"),
            "timestamp": convert_to_datetime(v.get("tmstmp")),
            "lat": float(v["lat"]),
            "lon": float(v["lon"]),
            "heading": int(v["hdg"]),
            "route": v.get("rt"),
            "destination": v.get("des"),
            "pattern_id": v.get("pid"),
            "distance_along_route_ft": int(v.get("pdist", 0)),
            "is_delayed": v.get("dly", False),
            "speed_mph": int(v.get("spd", 0)),
            "block_id": v.get("tablockid"),
            "trip_id": v.get("tatripid"),
            "origin_trip_no": v.get("origtatripno"),
            "zone": v.get("zone", ""),
            "mode": int(v.get("mode", 0)),  # 1 = bus
            "passenger_load": v.get("psgld"),
            "scheduled_start_sec": int(v.get("stst", 0)),
            "scheduled_start_date": v.get("stsd")
        })

    return pd.DataFrame(records)


# Helper to chunk routes in batches of 10
def chunked(iterable, size) -> Generator[list, None, None]:
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk

def fetch_all_bus_locations(time_resolution="s") -> pd.DataFrame:
    # Step 1: get all routes
    route_df = fetch_bus_routes().rename(columns={
        "route_id": "route"
    })

    route_df["route"] = route_df["route"].astype(str)

    # Step 2: chunk the route IDs and fetch vehicles
    route_ids = route_df["route"].tolist()
    all_records = []

    for route_chunk in chunked(route_ids, 10):
        df = fetch_bus_locations(route_chunk, time_resolution)
        if not df.empty:
            all_records.append(df)

    if not all_records:
        return pd.DataFrame()

    vehicles_df = pd.concat(all_records, ignore_index=True)

    # Step 3: merge vehicle data with route metadata
    full_df = vehicles_df.merge(route_df, on="route", how="left")

    return full_df


