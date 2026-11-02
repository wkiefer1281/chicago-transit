# scripts/get_transit_data.py
import logging

import pandas as pd

from backend.transit_modes.chicago_data_portal import fetch_cta_stations
from backend.transit_modes.cta_bus import fetch_all_bus_locations
from backend.transit_modes.cta_train import fetch_train_locations
from backend.transit_modes.metra import fetch_metra_stops, fetch_metra_vehicle_positions

log = logging.getLogger(__name__)

SOURCES = {
    "cta_station_df": fetch_cta_stations,
    "cta_train_df": fetch_train_locations,
    "cta_bus_df": fetch_all_bus_locations,
    "metra_station_df": fetch_metra_stops,
    "metra_train_df": fetch_metra_vehicle_positions,
}


def get_transit_data() -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Fetch every source independently.

    Returns (frames, failed). A source that raises yields an empty frame and is
    listed in `failed`, so one flaky API doesn't block the others.
    """
    frames: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for key, fetch in SOURCES.items():
        try:
            frames[key] = fetch()
            log.info("Fetched %s: %d rows", key, len(frames[key]))
        except Exception:
            log.exception("Fetching %s failed", key)
            frames[key] = pd.DataFrame()
            failed.append(key)
    return frames, failed
