"""The contract every live feed adapter follows.

An adapter is a module (see pipeline/live/austin.py) that provides:

    SOURCE   short id stored in live_incidents.source, e.g. "austin"
    LABEL    human-readable coverage, e.g. "Austin & Travis County, TX"
    SNAPSHOT True if each fetch returns *all currently active* incidents (typical for 511
             feeds): anything missing from a fetch is then marked cleared. False if the feed
             is incremental and reports status itself (Austin).
    fetch(since, get) -> list[dict]
             Raw records changed since `since` (UTC; snapshot feeds get None). Must only use
             the injected get(url) -> str (response body as text) for HTTP, so tests can run
             offline. Parse JSON/XML/RSS inside the adapter.
    parse(raw) -> dict | None
             One raw record -> a LiveIncident dict (keys below), or None to skip it.
"""
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

# Requires the tz database; on Windows that comes from the tzdata package (requirements-app.txt).
PACIFIC = ZoneInfo("America/Los_Angeles")

CATEGORIES = ("crash", "hazard", "stalled_vehicle", "closure", "fire", "other")
FIELDS = ("source_id", "category", "raw_type", "description", "road", "latitude", "longitude",
          "reported_at", "updated_at", "status")


class Adapter(Protocol):
    SOURCE: str
    LABEL: str
    SNAPSHOT: bool

    def fetch(self, since: datetime | None, get: Callable[[str], str]) -> list[dict]: ...

    def parse(self, raw: dict) -> dict | None: ...


def utc(value: str | None) -> datetime | None:
    """Parse an ISO timestamp to naive UTC. Values without an offset are assumed to be UTC
    already (Socrata marks UTC fields with a trailing Z)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def coordinate(lat, lon, bounds: tuple[float, float, float, float]) -> tuple[float | None, float | None]:
    """(lat, lon) if both parse and fall inside (min_lat, min_lon, max_lat, max_lon), else (None, None)."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    min_lat, min_lon, max_lat, max_lon = bounds
    return (lat, lon) if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon else (None, None)


def local_to_utc(local: datetime, zone: ZoneInfo) -> datetime:
    """Naive local wall-clock time in `zone` -> naive UTC. In the repeated autumn hour this
    picks the first (daylight) occurrence, zoneinfo's default (fold=0)."""
    if local.tzinfo:
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    return local.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(value: datetime, zone: ZoneInfo) -> datetime:
    """Naive UTC -> naive local wall-clock time in `zone` (for building source queries)."""
    return value.replace(tzinfo=timezone.utc).astimezone(zone).replace(tzinfo=None)
