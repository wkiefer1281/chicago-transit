import pandas as pd
from cta.client import CTAClient, Route
from cta.stations import Stations

# get train locations for each route
def train_locations(cta_client: CTAClient) -> pd.DataFrame:

    location_data = cta_client.locations([route for route in Route])
    df = location_data.to_frame()

    return df