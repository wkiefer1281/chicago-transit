# main.py
import json
import os
from dotenv import load_dotenv
from scripts.get_transit_data import get_transit_data
from backend.utilities.utilities import display_data, upload_data

def _load_secrets_from_json_env():
    secret_payload = os.getenv("CHICAGO_TRANSIT_SECRET_JSON")
    if not secret_payload:
        return
    try:
        values = json.loads(secret_payload)
    except json.JSONDecodeError:
        raise ValueError("CHICAGO_TRANSIT_SECRET_JSON is not valid JSON.")
    # Only set values that are missing to allow local overrides.
    for key in [
        "CHICAGO_APP_TOKEN",
        "CHICAGO_SECRET_TOKEN",
        "CTA_TRAIN_API_KEY",
        "CTA_BUS_API_KEY",
        "METRA_API_TOKEN",
    ]:
        if key in values and not os.getenv(key):
            os.environ[key] = str(values[key])

_load_secrets_from_json_env()
load_dotenv()  # Load other .env variables if present

def main():
    mode = "bq"
    data_frames = get_transit_data()

    if mode == "df":
        display_data(data_frames)
    elif mode == "bq":
        upload_data(data_frames)

if __name__ == "__main__":
    main()
