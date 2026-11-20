"""A property's timezone as a usable zone, with a safe fallback."""

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

log = logging.getLogger(__name__)

FALLBACK_ZONE = "UTC"


def property_zone(timezone_name: str) -> ZoneInfo:
    """The named zone; UTC (with a warning) when the stored name is not a real zone."""
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Unknown property timezone %r; using %s", timezone_name, FALLBACK_ZONE)
        return ZoneInfo(FALLBACK_ZONE)
