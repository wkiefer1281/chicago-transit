import io
import zipfile
from datetime import datetime

import pandas as pd
from google.transit import gtfs_realtime_pb2

from backend.transit_modes import metra
from backend.transit_modes.metra import (
    INCOMING_AT,
    IN_TRANSIT_TO,
    _derive_stops,
    _next_stop_updates,
    _scheduled_seconds,
)
from backend.utilities.timeutils import CHICAGO_TZ

NOW = 1_000_000


def _feed(*trains):
    """trains: (vehicle_id, route_id, [(stop_id, sequence, seconds_from_now), ...])"""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = NOW
    for i, (vehicle_id, route_id, stops) in enumerate(trains):
        update = feed.entity.add(id=str(i)).trip_update
        update.trip.trip_id = f"{route_id}_trip"
        update.trip.route_id = route_id
        update.vehicle.id = vehicle_id
        for stop_id, seq, eta in stops:
            stu = update.stop_time_update.add(stop_id=stop_id, stop_sequence=seq)
            stu.arrival.time = NOW + eta
    return feed


def _schedule(*rows):
    """rows: (trip_id, stop_id, 'HH:MM:SS') -> the timetable lookup, padded like Metra's files."""
    return _scheduled_seconds(pd.DataFrame(rows, columns=["trip_id", "stop_id", "arrival_time"]))


def _positions(**overrides):
    base = {
        "vehicle_id": ["v1"], "trip_id": [""], "route_id": [""], "start_time": [""], "start_date": [""],
        "stop_id": [""], "current_stop_sequence": [None], "current_status": pd.array([None], dtype="Int64"),
    }
    return pd.DataFrame({**base, **overrides})


def test_next_stop_is_the_earliest_upcoming_one():
    feed = _feed(("v1", "UP-N", [("PAST", 3, -300), ("LATER", 9, 900), ("NEXT", 5, 200)]))
    row = _next_stop_updates(feed).iloc[0]
    assert (row["update_stop_id"], row["update_stop_sequence"], row["eta_seconds"]) == ("NEXT", 5, 200)


def test_vehicles_without_upcoming_stops_are_skipped():
    feed = _feed(("v1", "UP-N", [("PAST", 3, -300)]), ("v2", "UP-N", []))
    assert _next_stop_updates(feed).empty


def test_blank_positions_are_filled_from_the_update():
    updates = _next_stop_updates(_feed(("v1", "UP-N", [("NEXT", 5, 600)])))
    out = _derive_stops(_positions(), updates).iloc[0]
    assert (out["route_id"], out["trip_id"], out["stop_id"], out["current_stop_sequence"]) == ("UP-N", "UP-N_trip", "NEXT", 5)
    assert out["current_status"] == IN_TRANSIT_TO
    assert out["current_status_source"] == "derived"


def test_arriving_soon_is_incoming():
    updates = _next_stop_updates(_feed(("v1", "UP-N", [("NEXT", 5, 60)])))
    assert _derive_stops(_positions(), updates).iloc[0]["current_status"] == INCOMING_AT


def test_reported_values_win():
    updates = _next_stop_updates(_feed(("v1", "UP-N", [("NEXT", 5, 600)])))
    positions = _positions(
        route_id=["MD-W"], stop_id=["REPORTED"], current_stop_sequence=[2], current_status=pd.array([1], dtype="Int64")
    )
    out = _derive_stops(positions, updates).iloc[0]
    assert (out["route_id"], out["stop_id"], out["current_stop_sequence"], out["current_status"]) == ("MD-W", "REPORTED", 2, 1)
    assert out["current_status_source"] == "reported"


def test_vehicle_without_an_update_stays_blank():
    out = _derive_stops(_positions(), _next_stop_updates(gtfs_realtime_pb2.FeedMessage())).iloc[0]
    assert out["stop_id"] == "" and out["route_id"] == ""
    assert pd.isna(out["current_status"]) and pd.isna(out["current_status_source"])


# The feed's start_date is a Chicago service day, and the timetable counts from its midnight.
DAY = "20261102"
MIDNIGHT = datetime(2026, 11, 2, tzinfo=CHICAGO_TZ).timestamp()


def _feed_at(clock, trip_id, stop_id, eta_epoch):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = int(clock)
    update = feed.entity.add(id="1").trip_update
    update.trip.trip_id = trip_id
    update.trip.start_date = DAY
    update.vehicle.id = "v1"
    update.stop_time_update.add(stop_id=stop_id, stop_sequence=4).arrival.time = int(eta_epoch)
    return feed


def _delay(minutes_late):
    """Delay computed for a train due at 08:00:00 that is predicted `minutes_late` behind that."""
    eta = MIDNIGHT + 8 * 3600 + minutes_late * 60
    feed = _feed_at(eta - 600, "T1", "STOP", eta)
    schedule = _schedule(("T1", "STOP", "08:00:00"))
    return _derive_stops(_positions(), _next_stop_updates(feed, schedule)).iloc[0]


def test_delay_is_prediction_minus_timetable():
    out = _delay(12)
    assert out["delay_minutes"] == 12 and out["is_delayed"]


def test_early_and_slightly_late_trains_are_not_delayed():
    assert not _delay(-3)["is_delayed"]
    assert not _delay(4)["is_delayed"]
    assert _delay(5)["is_delayed"]


def test_delay_is_unknown_without_a_matching_timetable_row():
    eta = MIDNIGHT + 8 * 3600
    out = _derive_stops(_positions(), _next_stop_updates(_feed_at(eta - 600, "T1", "STOP", eta), _schedule(("OTHER", "STOP", "08:00:00")))).iloc[0]
    assert pd.isna(out["delay_minutes"]) and pd.isna(out["is_delayed"])
    # ...and likewise when no timetable was loaded at all.
    out = _derive_stops(_positions(), _next_stop_updates(_feed_at(eta - 600, "T1", "STOP", eta))).iloc[0]
    assert pd.isna(out["delay_minutes"]) and pd.isna(out["is_delayed"])


def test_timetable_times_past_midnight_count_from_the_service_day():
    eta = MIDNIGHT + 25 * 3600 + 600  # 01:10 the next morning, for a 25:00:00 stop
    schedule = _schedule(("T1", "STOP", "25:00:00"))
    out = _derive_stops(_positions(), _next_stop_updates(_feed_at(eta - 600, "T1", "STOP", eta), schedule)).iloc[0]
    assert out["delay_minutes"] == 10


def test_static_files_are_stripped_of_padding(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("stop_times.txt", "trip_id, stop_id ,arrival_time\n SWS_SW812_V2_AA,  AURORA,08:42:00\n")
    monkeypatch.setattr(metra, "_download_gtfs_static", lambda: buf.getvalue())
    df = metra._load_gtfs_static_file("stop_times.txt")
    assert df.loc[0, "trip_id"] == "SWS_SW812_V2_AA" and df.loc[0, "stop_id"] == "AURORA"
