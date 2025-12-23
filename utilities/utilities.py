# utilities/utilities.py
import os
import pandas as pd
from pandas_gbq import to_gbq
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("BQ_PROJECT_ID")

def upload_df(df: pd.DataFrame, dataset: str, table: str):
    if not df.empty:
        full_table = f"{dataset}.{table}"
        to_gbq(df, full_table, project_id=PROJECT_ID, if_exists="replace")
        print(f"Uploaded {len(df)} rows to {full_table}")
