# server/metrics.py
import pandas as pd

# Official CTA line colors, so riders recognise each line at a glance.
CTA_LINE_COLORS = {
    "Red Line": "#c60c30",
    "Blue Line": "#00a1de",
    "Brown Line": "#62361b",
    "Green Line": "#009b3a",
    "Orange Line": "#f9461c",
    "Purple Line": "#522398",
    "Pink Line": "#e27ea6",
    "Yellow Line": "#f9e300",
}
# Metra's own route_color per line (routes.txt), keyed like the API's `route` (route_short_name).
METRA_LINE_COLORS = {
    "BNSF": "#29c233",
    "HC": "#550e0c",
    "MD-N": "#cc5500",
    "MD-W": "#f1ad0e",
    "ME": "#eb5c00",
    "NCS": "#9785bc",
    "RI": "#e02400",
    "SWS": "#0042a8",
    "UP-N": "#008000",
    "UP-NW": "#ffe600",
    "UP-W": "#fe8d81",
}
# Trains not running a scheduled trip (yard moves, deadheads) have no line.
METRA_COLOR = "#6b7280"
BUS_COLOR = "#0f766e"


def _flags(series: pd.Series) -> pd.Series:
    """Delayed flag as plain bool; missing counts as not delayed."""
    return series.eq(True)


def delayed_pct(df: pd.DataFrame) -> float:
    """Percent of vehicles flagged delayed (0.0 for an empty frame)."""
    if df.empty:
        return 0.0
    return float(_flags(df["is_delayed"]).mean() * 100)


def known_delayed_pct(df: pd.DataFrame) -> tuple[float | None, int]:
    """(% delayed, how many vehicles it is out of), counting only vehicles whose status is known.

    Unlike `delayed_pct`, a missing flag is not "on time": Metra only has one for trains with
    a prediction. The percent is None when nothing is known.
    """
    if df.empty:
        return None, 0
    known = df["is_delayed"].dropna()
    if known.empty:
        return None, 0
    return float(known.astype(bool).mean() * 100), len(known)


def delayed_by_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Vehicles, delayed count and delayed % per group, most-delayed first."""
    cols = [group_col, "vehicles", "delayed", "delayed_pct"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    flagged = df.assign(_delayed=_flags(df["is_delayed"]))
    out = (
        flagged.groupby(group_col)
        .agg(vehicles=("_delayed", "size"), delayed=("_delayed", "sum"))
        .reset_index()
    )
    out["delayed_pct"] = out["delayed"] / out["vehicles"] * 100
    return out.sort_values(["delayed_pct", "vehicles"], ascending=False, ignore_index=True)[cols]


def history_delay_pct(history: pd.DataFrame) -> pd.DataFrame:
    """Turn bucketed delayed/total counts into a delayed % per line per bucket."""
    if history.empty:
        return history.assign(delayed_pct=pd.Series(dtype=float))
    out = history.copy()
    out["delayed_pct"] = out["delayed"] / out["total"] * 100
    return out
