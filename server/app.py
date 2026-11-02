# server/app.py
"""JSON API over the BigQuery snapshots, plus the built web app when present.

Run: uvicorn server.app:app --reload   (the Vite dev server proxies /api here)
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from server import queries
from server.metrics import (
    BUS_COLOR,
    CTA_LINE_COLORS,
    METRA_COLOR,
    delayed_by_group,
    delayed_pct,
    history_delay_pct,
)

REFRESH_S = max(10, int(os.getenv("REFRESH_MS", "60000")) // 1000)
STALE_AFTER_MIN = 15  # the ETL runs every few minutes; older than this means it's stuck
MAX_POSITION_MINUTES = 180
MIN_BUS_SAMPLE = 5  # skip routes with too few buses to say anything about
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

# window -> (hours of history, bucket size in minutes)
HISTORY_WINDOWS = {"6h": (6, 15), "24h": (24, 30), "7d": (168, 180)}

app = FastAPI(title="Chicago Transit API")
app.add_middleware(GZipMiddleware, minimum_size=1024)


def records(df: pd.DataFrame, float_digits: int = 5) -> list[dict]:
    """DataFrame -> JSON-safe rows: NaN/NA become null, timestamps ISO strings."""
    if df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].map(lambda ts: None if pd.isna(ts) else ts.isoformat())
        elif pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(float_digits)
    out = out.astype(object).where(out.notna(), None)
    return [
        {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()}
        for row in out.to_dict("records")
    ]


@app.get("/api/meta")
def meta() -> dict:
    return {
        "refresh_s": REFRESH_S,
        "line_colors": CTA_LINE_COLORS,
        "bus_color": BUS_COLOR,
        "metra_color": METRA_COLOR,
        "history_windows": list(HISTORY_WINDOWS),
    }


@app.get("/api/summary")
def summary() -> dict:
    trains, buses, metra = queries.load_cta_trains(), queries.load_cta_buses(), queries.load_metra()
    stamps = [df["ingested_at"].max() for df in (trains, buses, metra) if not df.empty]
    updated = max(stamps).to_pydatetime() if stamps else None
    age_min = (datetime.now(timezone.utc) - updated).total_seconds() / 60 if updated else None

    by_route = delayed_by_group(buses, "route")
    by_route = by_route[by_route["vehicles"] >= MIN_BUS_SAMPLE].head(10)
    return {
        "updated_at": updated.isoformat() if updated else None,
        "age_minutes": age_min,
        "stale": age_min is None or age_min > STALE_AFTER_MIN,
        "kpis": {
            "trains": len(trains),
            "trains_delayed_pct": delayed_pct(trains),
            "buses": len(buses),
            "buses_delayed_pct": delayed_pct(buses),
            "metra": len(metra),
        },
        "trains_by_line": records(delayed_by_group(trains, "route")),
        "buses_by_route": records(by_route),
    }


@app.get("/api/positions")
def positions(minutes: int = Query(60, ge=5, le=MAX_POSITION_MINUTES)) -> dict:
    """Vehicle positions per ETL snapshot, oldest first, for replay and tweening."""
    snapshots: dict[str, dict[str, list]] = {}
    for mode in ("trains", "buses", "metra"):
        df = queries.load_positions(mode, minutes)
        if df.empty:
            continue
        for ingested_at, group in df.groupby("ingested_at", sort=True):
            snap = snapshots.setdefault(
                ingested_at.isoformat(), {"trains": [], "buses": [], "metra": []}
            )
            snap[mode] = records(group.drop(columns="ingested_at"))
    return {"snapshots": [{"t": t, **snap} for t, snap in sorted(snapshots.items())]}


@app.get("/api/delay-history")
def delay_history(window: str = "24h") -> dict:
    if window not in HISTORY_WINDOWS:
        raise HTTPException(422, f"window must be one of {list(HISTORY_WINDOWS)}")
    hours, bucket = HISTORY_WINDOWS[window]
    history = history_delay_pct(queries.load_train_delay_history(hours, bucket))
    return {"window": window, "rows": records(history, float_digits=2)}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# Registered last so it never shadows /api. Absent in dev (Vite serves the app instead).
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
