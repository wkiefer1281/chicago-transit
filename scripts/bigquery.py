from dotenv import load_dotenv
import pandas as pd
import pandas_gbq
from cta.client import CTAClient, Route
from cta.stations import Stations

load_dotenv()

def train_locations(cta_client: CTAClient) -> pd.DataFrame:

    all_location_response = cta_client.locations([route for route in Route])
    df = all_location_response.to_frame()

    return df


if __name__ == "__main__":
    cta_client = CTAClient()
    df = train_locations(cta_client=cta_client)

# push results to BQ
project_id = "eternal-outlook-451201-d1"
pandas_gbq.to_gbq(df, "chicago_transit.train_locations", project_id=project_id, if_exists="replace")