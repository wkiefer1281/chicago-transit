# chicago_api.py
import os
from sodapy import Socrata
import pandas as pd

def get_station_names():
    # Use your app token here
    app_token = os.getenv("CHICAGO_APP_TOKEN")
    
    # Initialize the client with the app token
    client = Socrata("data.cityofchicago.org", app_token)

    # Fetch station data (you can increase the limit or handle pagination if needed)
    results = client.get("8pix-ypme", limit=2000)

    # Convert the results into a pandas DataFrame
    results_df = pd.DataFrame.from_records(results)

    return results_df
