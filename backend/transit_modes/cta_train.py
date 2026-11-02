# cta_train.py
import xml.etree.ElementTree as ET

import pandas as pd

from backend.config import require_env
from backend.utilities import http
from backend.utilities.timeutils import parse_cta_time

BASE_URL = "https://lapi.transitchicago.com/api/1.0"
REQUEST_TIMEOUT = 30

# Mapping for route identifiers to full color names
route_map = {
    "red": "Red Line",
    "blue": "Blue Line",
    "brn": "Brown Line",
    "g": "Green Line",
    "org": "Orange Line",
    "p": "Purple Line",
    "pink": "Pink Line",
    "y": "Yellow Line",
}

TRAIN_ROUTES = ["Red", "Blue", "Brn", "G", "Org", "P", "Pink", "Y"]

TIME_COLUMNS = ["predicted_time", "arrival_time"]


def _flag(value: str | None) -> bool | None:
    return None if value is None else value.strip() == "1"


def _float(value: str | None) -> float | None:
    return float(value) if value else None


def _int(value: str | None) -> int | None:
    return int(value) if value else None


def parse_train_positions(xml_text: str) -> pd.DataFrame:
    """Parse a Train Tracker ttpositions response into a DataFrame."""
    root = ET.fromstring(xml_text)
    error = root.findtext("errCd")
    if error not in (None, "0"):
        raise RuntimeError(f"CTA Train Tracker error {error}: {root.findtext('errNm')}")

    trains = []
    for route in root.findall(".//route"):
        # Match case-insensitively: the API returns "red", "brn", etc.
        route_key = (route.attrib.get("name") or "").lower()
        full_route_name = route_map.get(route_key, route.attrib.get("name"))

        for train in route.findall("train"):
            trains.append({
                "route": full_route_name,
                "run_number": train.findtext("rn"),
                "destination_station_id": train.findtext("destSt"),
                "destination_station_name": train.findtext("destNm"),
                "train_direction": train.findtext("trDr"),
                "next_station_id": train.findtext("nextStaId"),
                "next_stop_id": train.findtext("nextStpId"),
                "next_station_name": train.findtext("nextStaNm"),
                "predicted_time": parse_cta_time(train.findtext("prdt")),
                "arrival_time": parse_cta_time(train.findtext("arrT")),
                "is_approaching": _flag(train.findtext("isApp")),
                "is_delayed": _flag(train.findtext("isDly")),
                "flags": train.findtext("flags"),
                "latitude": _float(train.findtext("lat")),
                "longitude": _float(train.findtext("lon")),
                "heading": _int(train.findtext("heading")),
            })

    df = pd.DataFrame(trains)
    for col in TIME_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df


def fetch_train_locations() -> pd.DataFrame:
    """Fetch current vehicle locations for every CTA rail line."""
    response = http.get(
        f"{BASE_URL}/ttpositions.aspx",
        params={"rt": ",".join(TRAIN_ROUTES), "key": require_env("CTA_TRAIN_API_KEY")},
        timeout=REQUEST_TIMEOUT,
    )
    return parse_train_positions(response.text)
