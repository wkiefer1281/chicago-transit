# cta_bus.py
from itertools import islice
from typing import Generator

import pandas as pd

from backend.config import require_env
from backend.utilities import http
from backend.utilities.timeutils import parse_cta_time

BASE_URL = "https://www.ctabustracker.com/bustime/api/v3"
REQUEST_TIMEOUT = 30
MAX_ROUTES_PER_REQUEST = 10  # getvehicles accepts at most 10 routes


def _get(endpoint: str, **params) -> dict:
    response = http.get(
        f"{BASE_URL}/{endpoint}",
        params={"key": require_env("CTA_BUS_API_KEY"), "format": "json", **params},
        timeout=REQUEST_TIMEOUT,
    )
    return response.json().get("bustime-response", {})


def fetch_bus_routes() -> pd.DataFrame:
    routes = _get("getroutes").get("routes", [])
    if not routes:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "route_id": r["rt"],
            "route_name": r["rtnm"],
            "route_color": r["rtclr"],
            "route_display": r["rtdd"],
        }
        for r in routes
    ])


def _to_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "y", "yes"}


def _to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_vehicles(vehicles: list[dict]) -> pd.DataFrame:
    records = []
    for v in vehicles:
        try:
            lat, lon = float(v["lat"]), float(v["lon"])
        except (KeyError, TypeError, ValueError):
            continue  # a vehicle without a position is useless here
        records.append({
            "vehicle_id": v.get("vid"),
            "timestamp": parse_cta_time(v.get("tmstmp")),
            "lat": lat,
            "lon": lon,
            "heading": _to_int(v.get("hdg")),
            "route": v.get("rt"),
            "destination": v.get("des"),
            "pattern_id": v.get("pid"),
            "distance_along_route_ft": _to_int(v.get("pdist")),
            "is_delayed": _to_bool(v.get("dly", False)),
            "speed_mph": _to_int(v.get("spd")),
            "block_id": v.get("tablockid"),
            "trip_id": v.get("tatripid"),
            "origin_trip_no": v.get("origtatripno"),
            "zone": v.get("zone", ""),
            "mode": _to_int(v.get("mode")),  # 1 = bus
            "passenger_load": v.get("psgld"),
            "scheduled_start_sec": _to_int(v.get("stst")),
            "scheduled_start_date": v.get("stsd"),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        for col in ("heading", "distance_along_route_ft", "speed_mph", "mode", "scheduled_start_sec"):
            df[col] = df[col].astype("Int64")
    return df


def fetch_bus_locations(routes: list[str] | None = None, time_resolution: str = "s") -> pd.DataFrame:
    """Fetch current vehicle positions (time_resolution "s" = second resolution)."""
    params = {"tmres": time_resolution}
    if routes:
        params["rt"] = ",".join(routes[:MAX_ROUTES_PER_REQUEST])

    vehicles = _get("getvehicles", **params).get("vehicle")
    if not vehicles:
        return pd.DataFrame()
    return parse_vehicles(vehicles)


def chunked(iterable, size) -> Generator[list, None, None]:
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk


def fetch_all_bus_locations(time_resolution: str = "s") -> pd.DataFrame:
    route_df = fetch_bus_routes()
    if route_df.empty:
        return pd.DataFrame()
    route_df = route_df.rename(columns={"route_id": "route"})
    route_df["route"] = route_df["route"].astype(str)

    frames = []
    for route_chunk in chunked(route_df["route"].tolist(), MAX_ROUTES_PER_REQUEST):
        df = fetch_bus_locations(route_chunk, time_resolution)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    vehicles_df = pd.concat(frames, ignore_index=True)
    return vehicles_df.merge(route_df, on="route", how="left")
