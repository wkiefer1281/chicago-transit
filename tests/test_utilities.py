from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

from backend.utilities.utilities import INGESTED_AT, TABLES, _job_config, _prepare


def test_prepare_adds_ingested_at_and_fixes_null_columns():
    df = pd.DataFrame({"a": [1, 2], "all_null": [None, None]})
    out = _prepare(df, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert (out[INGESTED_AT] == pd.Timestamp("2026-01-01", tz="UTC")).all()
    assert str(out["all_null"].dtype) == "string"
    assert INGESTED_AT not in df.columns  # input untouched


def test_vehicle_tables_append_partitioned_stations_replace():
    for spec in TABLES.values():
        cfg = _job_config(spec)
        if spec.append:
            assert cfg.write_disposition == bigquery.WriteDisposition.WRITE_APPEND
            assert cfg.time_partitioning.field == INGESTED_AT
        else:
            assert cfg.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert {s.name for s in TABLES.values() if s.append} == {
        "cta_train_locations", "cta_bus_locations", "metra_train_locations",
    }
