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
METRA_COLOR = "#2563eb"
BUS_COLOR = "#0f766e"


def _flags(series: pd.Series) -> pd.Series:
    """Delayed flag as plain bool; missing counts as not delayed."""
    return series.eq(True)


def delayed_pct(df: pd.DataFrame) -> float:
    """Percent of vehicles flagged delayed (0.0 for an empty frame)."""
    if df.empty:
        return 0.0
    return float(_flags(df["is_delayed"]).mean() * 100)


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
