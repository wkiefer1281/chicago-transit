# backend/config.py
"""Environment/config loading. Everything is read lazily so that secrets injected
via CHICAGO_TRANSIT_SECRET_JSON are visible no matter when a module is imported."""
import json
import os

from dotenv import load_dotenv

SECRET_KEYS = (
    "CHICAGO_APP_TOKEN",
    "CHICAGO_SECRET_TOKEN",
    "CTA_TRAIN_API_KEY",
    "CTA_BUS_API_KEY",
    "METRA_API_TOKEN",
)

DEFAULT_BQ_DATASET = "transit_data"

_loaded = False


def load_env() -> None:
    """Load .env and the optional secrets JSON into os.environ (idempotent).

    Real environment variables win over both, so local overrides keep working.
    """
    global _loaded
    if _loaded:
        return
    load_dotenv(".env")
    payload = os.getenv("CHICAGO_TRANSIT_SECRET_JSON")
    if payload:
        try:
            values = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("CHICAGO_TRANSIT_SECRET_JSON is not valid JSON.") from exc
        for key in SECRET_KEYS:
            if key in values and not os.getenv(key):
                os.environ[key] = str(values[key])
    _loaded = True


def get_env(name: str, default: str | None = None) -> str | None:
    load_env()
    return os.getenv(name, default)


def require_env(name: str) -> str:
    value = get_env(name)
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value


def bq_project() -> str | None:
    return get_env("BQ_PROJECT_ID")


def bq_dataset() -> str:
    return get_env("BQ_DATASET", DEFAULT_BQ_DATASET)
