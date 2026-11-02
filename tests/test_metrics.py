import pandas as pd

from server.metrics import delayed_by_group, delayed_pct, history_delay_pct


def test_delayed_pct_and_empty():
    assert delayed_pct(pd.DataFrame({"is_delayed": [True, False, False, False]})) == 25.0
    assert delayed_pct(pd.DataFrame({"is_delayed": [None, True]})) == 50.0
    assert delayed_pct(pd.DataFrame()) == 0.0


def test_delayed_by_group_sorted():
    df = pd.DataFrame({
        "route": ["Red", "Red", "Blue", "Blue", "Blue"],
        "is_delayed": [True, False, False, False, False],
    })
    out = delayed_by_group(df, "route")
    assert list(out["route"]) == ["Red", "Blue"]
    assert out.loc[0, "delayed_pct"] == 50.0
    assert out.loc[1, "vehicles"] == 3
    assert delayed_by_group(pd.DataFrame(), "route").empty


def test_history_pct_is_pooled_ratio():
    h = pd.DataFrame({"route": ["Red"], "delayed": [3], "total": [12]})
    assert history_delay_pct(h)["delayed_pct"].iloc[0] == 25.0
    assert history_delay_pct(pd.DataFrame(columns=["delayed", "total"])).empty
