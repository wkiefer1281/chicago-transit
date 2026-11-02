import json
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import server.app as api
from server import queries

NOW = pd.Timestamp(datetime.now(timezone.utc))
EARLIER = NOW - pd.Timedelta(minutes=5)


def _trains():
    return pd.DataFrame({
        "run_number": ["1", "2", "3"], "route": ["Red Line", "Red Line", "Blue Line"],
        "next_station_name": ["A", "B", None], "destination_station_name": ["Howard", "95th", "O'Hare"],
        "is_delayed": [True, False, False], "lat": [41.9, 41.8, 41.95], "lon": [-87.6, -87.65, -87.9],
        "predicted_time": [NOW] * 3, "arrival_time": [NOW] * 3, "ingested_at": [NOW] * 3,
    })


def _buses():
    return pd.DataFrame({
        "route": ["22"] * 6, "route_name": ["Clark"] * 6, "destination": ["Howard"] * 6,
        "is_delayed": [True, False, False, False, False, False],
        "speed_mph": pd.array([10, None, 5, 0, 3, 2], dtype="Int64"),
        "vehicle_id": list("abcdef"), "timestamp": [NOW] * 6, "lat": [41.9] * 6, "lon": [-87.7] * 6,
        "ingested_at": [NOW] * 6,
    })


def _metra():
    return pd.DataFrame({
        "route_id": ["", "UP-N"], "route_short_name": [None, "UP-N"], "trip_headsign": [None, None],
        "vehicle_id": ["m1", "m2"], "vehicle_label": ["101", None],
        "current_status": pd.array([None, 1], dtype="Int64"),
        "is_delayed": pd.array([None, True], dtype="boolean"), "delay_minutes": [None, 9.0],
        "timestamp": [NOW] * 2, "lat": [42.0, 42.1], "lon": [-87.8, -87.7], "ingested_at": [NOW] * 2,
    })


def _history():
    return pd.DataFrame({
        "bucket": [NOW - pd.Timedelta(minutes=30), NOW] * 2, "route": ["Red Line"] * 2 + ["Blue Line"] * 2,
        "delayed": [1, 0, 0, 2], "total": [20, 21, 10, 10], "snapshots": [6] * 4,
    })


def _positions(mode: str, minutes: int) -> pd.DataFrame:
    if mode != "trains":
        return pd.DataFrame()
    return pd.DataFrame({
        "id": ["Red Line|1", "Red Line|1"], "route": ["Red Line"] * 2, "destination": ["Howard"] * 2,
        "next_stop": ["A", None], "is_delayed": [False, True],
        "lat": [41.9, 41.91], "lon": [-87.6, -87.61], "ingested_at": [EARLIER, NOW],
    })


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(queries, "load_cta_trains", _trains)
    monkeypatch.setattr(queries, "load_cta_buses", _buses)
    monkeypatch.setattr(queries, "load_metra", _metra)
    monkeypatch.setattr(queries, "load_train_delay_history", lambda hours, bucket: _history())
    monkeypatch.setattr(queries, "load_positions", _positions)
    return TestClient(api.app)


@pytest.fixture
def empty_client(monkeypatch):
    empty = pd.DataFrame()
    for name in ("load_cta_trains", "load_cta_buses", "load_metra"):
        monkeypatch.setattr(queries, name, lambda: empty)
    monkeypatch.setattr(queries, "load_train_delay_history", lambda hours, bucket: empty)
    monkeypatch.setattr(queries, "load_positions", lambda mode, minutes: empty)
    return TestClient(api.app)


def test_meta_exposes_colors(client):
    body = client.get("/api/meta").json()
    assert body["line_colors"]["Red Line"] == "#c60c30"
    assert body["metra_line_colors"]["UP-N"] == "#008000"
    assert body["history_windows"] == ["6h", "24h", "7d"]


def test_summary_with_data(client):
    body = client.get("/api/summary").json()
    assert body["kpis"]["trains"] == 3
    assert body["kpis"]["trains_delayed_pct"] == pytest.approx(33.33, abs=0.01)
    assert body["kpis"]["metra"] == 2
    # Only the one train with a known status counts, so the unknown one isn't "on time".
    assert body["kpis"]["metra_delayed_pct"] == 100 and body["kpis"]["metra_tracked"] == 1
    assert body["stale"] is False
    assert [r["route"] for r in body["trains_by_line"]] == ["Red Line", "Blue Line"]
    assert body["buses_by_route"][0]["route"] == "22"


def test_summary_without_data(empty_client):
    body = empty_client.get("/api/summary").json()
    assert body["updated_at"] is None and body["stale"] is True
    assert body["kpis"]["trains"] == 0
    assert body["kpis"]["metra_delayed_pct"] is None and body["kpis"]["metra_tracked"] == 0
    assert body["trains_by_line"] == []


def test_summary_flags_stale_data(client, monkeypatch):
    old = NOW - pd.Timedelta(minutes=60)
    monkeypatch.setattr(queries, "load_cta_trains", lambda: _trains().assign(ingested_at=old))
    monkeypatch.setattr(queries, "load_cta_buses", lambda: pd.DataFrame())
    monkeypatch.setattr(queries, "load_metra", lambda: pd.DataFrame())
    assert client.get("/api/summary").json()["stale"] is True


def test_positions_are_grouped_by_snapshot_oldest_first(client):
    snaps = client.get("/api/positions", params={"minutes": 30}).json()["snapshots"]
    assert [len(s["trains"]) for s in snaps] == [1, 1]
    assert snaps[0]["t"] < snaps[1]["t"]
    assert snaps[0]["trains"][0]["next_stop"] == "A"
    assert snaps[1]["trains"][0]["next_stop"] is None  # NaN must serialize as null
    assert snaps[0]["buses"] == [] and snaps[0]["metra"] == []


def test_positions_without_data_and_bad_window(empty_client):
    assert empty_client.get("/api/positions").json() == {"snapshots": []}
    assert empty_client.get("/api/positions", params={"minutes": 100000}).status_code == 422


def test_delay_history(client):
    rows = client.get("/api/delay-history", params={"window": "6h"}).json()["rows"]
    assert {r["route"] for r in rows} == {"Red Line", "Blue Line"}
    assert rows[0]["delayed_pct"] == 5.0
    assert client.get("/api/delay-history", params={"window": "1y"}).status_code == 422


def test_records_handle_missing_values():
    df = pd.DataFrame({
        "a": pd.array([1, None], dtype="Int64"),
        "b": [1.23456789, float("nan")],
        "c": [NOW, pd.NaT],
    })
    out = api.records(df)
    json.dumps(out, allow_nan=False)  # must be strict-JSON serializable
    assert out[1] == {"a": None, "b": None, "c": None}
    assert out[0]["b"] == 1.23457 and isinstance(out[0]["a"], int)
