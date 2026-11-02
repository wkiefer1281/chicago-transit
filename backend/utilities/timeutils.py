# backend/utilities/timeutils.py
from datetime import datetime
from zoneinfo import ZoneInfo

CHICAGO_TZ = ZoneInfo("America/Chicago")

# CTA Bus Tracker uses "YYYYMMDD HH:MM[:SS]"; Train Tracker uses ISO "YYYY-MM-DDTHH:MM:SS".
# Both are naive Chicago local time.
_CTA_FORMATS = ("%Y%m%d %H:%M:%S", "%Y%m%d %H:%M", "%Y-%m-%dT%H:%M:%S")


def parse_cta_time(value: str | None) -> datetime | None:
    """Parse a CTA timestamp (naive Chicago local time) into an aware datetime."""
    if not value:
        return None
    for fmt in _CTA_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=CHICAGO_TZ)
        except ValueError:
            continue
    return None
