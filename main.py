# main.py
import logging
import sys
from datetime import datetime, timezone

from backend.config import get_env, load_env
from backend.utilities.utilities import display_data, upload_data
from scripts.get_transit_data import get_transit_data

log = logging.getLogger("main")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_env()
    mode = get_env("OUTPUT_MODE", "bq").lower()
    if mode not in {"bq", "df"}:
        raise ValueError(f"OUTPUT_MODE must be 'bq' or 'df', got {mode!r}")

    ingested_at = datetime.now(timezone.utc)  # one timestamp per run -> consistent snapshots
    data_frames, failed = get_transit_data()

    if mode == "df":
        display_data(data_frames)
    else:
        failed += upload_data(data_frames, ingested_at)

    if failed:
        log.error("Run finished with failures: %s", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
