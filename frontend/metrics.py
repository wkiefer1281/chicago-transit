# frontend/metrics.py
from typing import Dict, Any

import pandas as pd


def build_cta_trains_metrics(trains_df: pd.DataFrame) -> Dict[str, Any]:
    if trains_df.empty:
        return {"count": 0, "delayed_pct": 0.0, "top_routes": pd.Series(dtype=int)}
    per_route = trains_df.groupby("route").size().sort_values(ascending=False)
    delayed_pct = trains_df["is_delayed"].mean() * 100
    return {
        "count": len(trains_df),
        "delayed_pct": delayed_pct,
        "top_routes": per_route.head(5),
    }


def build_cta_buses_metrics(buses_df: pd.DataFrame) -> Dict[str, Any]:
    if buses_df.empty:
        return {"count": 0, "delayed_pct": 0.0, "top_routes": pd.Series(dtype=int)}
    per_route = buses_df.groupby("route").size().sort_values(ascending=False)
    delayed_pct = buses_df["is_delayed"].mean() * 100
    return {
        "count": len(buses_df),
        "delayed_pct": delayed_pct,
        "top_routes": per_route.head(5),
    }
