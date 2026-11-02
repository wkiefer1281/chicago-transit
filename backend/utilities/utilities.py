# utilities/utilities.py
import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from google.cloud import bigquery

from backend.config import bq_dataset, bq_project

log = logging.getLogger(__name__)

INGESTED_AT = "ingested_at"


@dataclass(frozen=True)
class TableSpec:
    name: str
    # History tables get one batch of rows appended per run; reference tables are replaced.
    append: bool


TABLES: dict[str, TableSpec] = {
    "cta_station_df": TableSpec("cta_stations", append=False),
    "cta_train_df": TableSpec("cta_train_locations", append=True),
    "cta_bus_df": TableSpec("cta_bus_locations", append=True),
    "metra_station_df": TableSpec("metra_stations", append=False),
    "metra_train_df": TableSpec("metra_train_locations", append=True),
}


def _prepare(df: pd.DataFrame, ingested_at: datetime) -> pd.DataFrame:
    df = df.copy()
    df[INGESTED_AT] = pd.Timestamp(ingested_at).tz_convert("UTC")
    # An all-null object column has no inferable Arrow type; load it as STRING.
    for col in df.columns[df.dtypes == object]:
        if df[col].isna().all():
            df[col] = df[col].astype("string")
    return df


def _job_config(spec: TableSpec) -> bigquery.LoadJobConfig:
    if spec.append:
        return bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
            time_partitioning=bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field=INGESTED_AT
            ),
        )
    return bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)


def upload_df(
    client: bigquery.Client,
    df: pd.DataFrame,
    dataset: str,
    spec: TableSpec,
    ingested_at: datetime,
) -> int:
    """Load df into dataset.table and return the number of rows written."""
    if df.empty:
        log.warning("No rows for %s; skipping upload.", spec.name)
        return 0
    table_id = f"{client.project}.{dataset}.{spec.name}"
    job = client.load_table_from_dataframe(
        _prepare(df, ingested_at), table_id, job_config=_job_config(spec)
    )
    job.result()
    log.info("Loaded %d rows into %s (%s)", len(df), table_id, "append" if spec.append else "replace")
    return len(df)


def display_data(data_frames: dict) -> None:
    for name, df in data_frames.items():
        print(f"{name} ({len(df)} rows)")
        print(df.head())


def upload_data(data_frames: dict, ingested_at: datetime, dataset: str | None = None) -> list[str]:
    """Upload every known frame; returns the names of tables that failed."""
    client = bigquery.Client(project=bq_project())
    dataset = dataset or bq_dataset()
    client.create_dataset(bigquery.Dataset(f"{client.project}.{dataset}"), exists_ok=True)
    failed = []
    for key, spec in TABLES.items():
        try:
            upload_df(client, data_frames[key], dataset, spec, ingested_at)
        except Exception:
            log.exception("Upload to %s failed", spec.name)
            failed.append(spec.name)
    return failed
