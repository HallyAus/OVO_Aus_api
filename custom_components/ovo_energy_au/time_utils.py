"""Timezone-stable parsing for OVO's Australian energy periods."""
from __future__ import annotations

from datetime import datetime

from .const import AU_TIMEZONE


def parse_ovo_datetime(value: object) -> datetime | None:
    """Keep offsets; interpret offset-free API wall times in Australia/Sydney."""
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=AU_TIMEZONE)
        return result.astimezone(AU_TIMEZONE)
    except (ValueError, OverflowError):
        return None
