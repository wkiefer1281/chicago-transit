# cta_train.py
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import requests
from dotenv import load_dotenv
import os
from backend.transit_modes.chicago_data_portal import fetch_cta_station_names

BASE_URL = "http://lapi.transitchicago.com/api/1.0"

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys from .env file
cta_train_api_key = os.getenv('CTA_TRAIN_API_KEY')

# Mapping for route identifiers to full color names
route_map = {
    "red": "Red Line",
    "blue": "Blue Line",
    "brn": "Brown Line",
    "g": "Green Line",
    "org": "Orange Line",
    "p": "Purple Line",
    "pink": "Pink Line",
    "y": "Yellow Line"
}

# Get the station names from the DataFrame
station_names_df = fetch_cta_station_names()

# Create a dictionary for fast lookup (station_id -> station_name)
station_id_to_name = pd.Series(station_names_df.stop_name.values, index=station_names_df.stop_id).to_dict()

def get_station_name(station_id):
    # Return the station name or 'Unknown' if the station_id doesn't exist
    return station_id_to_name.get(station_id, "Unknown Station")

# Helper function to convert time string to datetime in the format "YYYYMMDD HH:MM:SS"
def convert_to_datetime(t: str) -> datetime | None:
    for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d %H:%M"):
        try:
            dt = datetime.strptime(t, fmt)
            return dt.astimezone()  # Converts to system local timezone
        except (ValueError, TypeError):
            continue
    return None

def fetch_train_locations():
    """Fetch current vehicle locations."""
    url = f"{BASE_URL}/ttpositions.aspx"
    routes = ["Red", "Blue", "Brn", "G", "Org", "P", "Pink", "Y"]
    routes_param = ",".join(routes)

    params = {
        "rt": routes_param,
        "key": cta_train_api_key
    }

    response = requests.get(url, params=params)  # Send the request
    response.raise_for_status()  # Raise an error if the request fails
    xml_data = response.text  # Return the raw XML response   

    # Parse the XML response
    root = ET.fromstring(xml_data)
    trains = []

    # Find all route elements
    for route in root.findall(".//route"):
        route_name = route.attrib.get("name")  # Get the route name (e.g., "Red", "Blue", etc.)

        # Map the route identifier to the full route name
        full_route_name = route_map.get(route_name, route_name)  # Default to route_name if not found in the map

        # Loop through each train in the route
        for train in route.findall(".//train"):
            train_info = {
                "route": full_route_name,  # Use the full route name
                "run_number": train.find("rn").text,  # Train run number
                "destination_station_id": train.find("destSt").text,  # Destination station ID
                "destination_station_name": train.find("destNm").text,  # Destination station name
                "train_direction": train.find("trDr").text,  # Train direction
                "next_station_id": train.find("nextStaId").text,  # Next station ID
                "next_stop_id": train.find("nextStpId").text,  # Next stop ID
                "next_station_name": train.find("nextStaNm").text,  # Next station name
                "predicted_time": convert_to_datetime(train.find("prdt").text) if train.find("prdt") is not None else None,  # Predicted time
                "arrival_time": convert_to_datetime(train.find("arrT").text) if train.find("arrT") is not None else None,  # Arrival time
                "is_approaching": train.find("isApp").text,  # Is the train approaching?
                "is_delayed": train.find("isDly").text,  # Is the train delayed?
                "flags": train.find("flags").text,  # Flags
                "latitude": float(train.find("lat").text),  # Train latitude
                "longitude": float(train.find("lon").text),  # Train longitude
                "heading": int(train.find("heading").text)  # Train heading/direction
            }

            # Add the train information to the list
            trains.append(train_info)

    # Convert the list of trains into a DataFrame
    df = pd.DataFrame(trains)
    return df
