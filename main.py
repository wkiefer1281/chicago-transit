import pandas_gbq
from cta.client import CTAClient
from scripts.scripts import train_locations

def main():
    # get CTA client
    cta_client = CTAClient()

    # call scripts
    df = train_locations(cta_client=cta_client)

    # push results to BQ
    project_id = "eternal-outlook-451201-d1"
    pandas_gbq.to_gbq(df, "chicago_transit.train_locations", project_id=project_id, if_exists="replace")

main()

