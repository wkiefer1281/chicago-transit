# scripts/get_transit_data.py

from backend.transit_modes.chicago_data_portal import fetch_cta_stations
from backend.transit_modes.cta_train import fetch_train_locations
from backend.transit_modes.cta_bus import fetch_all_bus_locations
from backend.transit_modes.metra import fetch_metra_vehicle_positions, fetch_metra_stops

def get_transit_data():
    # metra
    metra_station_df = fetch_metra_stops()
    metra_train_df = fetch_metra_vehicle_positions()
    # cta
    cta_station_df = fetch_cta_stations()
    cta_train_df = fetch_train_locations()
    cta_bus_df = fetch_all_bus_locations()

    return {
        "cta_station_df": cta_station_df,
        "cta_train_df": cta_train_df,
        "cta_bus_df": cta_bus_df,
        "metra_station_df": metra_station_df,
        "metra_train_df": metra_train_df,
    }
