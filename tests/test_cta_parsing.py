import pandas as pd

from backend.transit_modes.cta_bus import parse_vehicles
from backend.transit_modes.cta_train import parse_train_positions

TRAIN_XML = """<ctatt><tmst>2026-07-15T14:30:00</tmst><errCd>0</errCd><errNm/>
<route name="red"><train>
 <rn>811</rn><destSt>30173</destSt><destNm>Howard</destNm><trDr>1</trDr>
 <nextStaId>41320</nextStaId><nextStpId>30249</nextStpId><nextStaNm>Belmont</nextStaNm>
 <prdt>2026-07-15T14:29:55</prdt><arrT>2026-07-15T14:31:55</arrT>
 <isApp>1</isApp><isDly>0</isDly><flags/><lat>41.9</lat><lon>-87.6</lon><heading>358</heading>
</train></route>
<route name="brn"><train>
 <rn>401</rn><destSt>30249</destSt><destNm>Loop</destNm><trDr>5</trDr>
 <nextStaId>1</nextStaId><nextStpId>2</nextStpId><nextStaNm>Merchandise Mart</nextStaNm>
 <prdt>2026-07-15T14:29:55</prdt><arrT>2026-07-15T14:33:00</arrT>
 <isApp>0</isApp><isDly>1</isDly><lat>41.88</lat><lon>-87.63</lon><heading>90</heading>
</train></route></ctatt>"""


def test_train_parsing():
    df = parse_train_positions(TRAIN_XML)
    assert list(df["route"]) == ["Red Line", "Brown Line"]
    assert list(df["is_delayed"]) == [False, True]
    assert list(df["is_approaching"]) == [True, False]
    assert str(df["predicted_time"].dt.tz) == "UTC"
    # 14:29:55 CDT == 19:29:55 UTC
    assert df["predicted_time"].iloc[0].hour == 19
    assert df["flags"].iloc[1] is None  # missing element tolerated


def test_train_api_error_raises():
    xml = "<ctatt><errCd>101</errCd><errNm>Invalid API key</errNm></ctatt>"
    try:
        parse_train_positions(xml)
    except RuntimeError as exc:
        assert "Invalid API key" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_no_trains_gives_empty_frame():
    assert parse_train_positions("<ctatt><errCd>0</errCd></ctatt>").empty


def test_bus_parsing_handles_missing_and_bad_fields():
    vehicles = [
        {"vid": "1", "tmstmp": "20260715 14:30", "lat": "41.9", "lon": "-87.6", "hdg": "180",
         "rt": "22", "des": "Clark", "dly": True, "spd": "12", "pdist": "100", "mode": 1},
        {"vid": "2", "tmstmp": "20260715 14:30", "lat": "41.8", "lon": "-87.7", "rt": "9"},  # no hdg/spd
        {"vid": "3", "rt": "9"},  # no position: dropped
    ]
    df = parse_vehicles(vehicles)
    assert list(df["vehicle_id"]) == ["1", "2"]
    assert list(df["is_delayed"]) == [True, False]
    assert df["speed_mph"].isna().tolist() == [False, True]
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert df["heading"].dtype == "Int64"


def test_bus_parsing_all_dropped_is_empty():
    assert parse_vehicles([{"vid": "3"}]).empty
