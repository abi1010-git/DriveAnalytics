"""Seattle "Real Time Fire 911 Calls" (data.seattle.gov, kzjm-xkqj; served from cos-data.seattle.gov).

Every Seattle Fire Department dispatch since 2003 (~2.2M rows), updated every few minutes.
Checked Nov 2026:
- fields: incident_number, type, datetime, address, latitude, longitude, report_location
- `datetime` is Pacific LOCAL time with no zone (e.g. "2026-11-15T21:44:00.000"), so `since`
  is converted to Pacific for the query and parsed times back to naive UTC
- `type` is a fixed dispatch code list (271 values); only the traffic-related ones below are
  fetched, filtered server-side. Freeway medical/brush calls ("Aid Response Freeway", "Brush Fire
  Freeway", "Fire Response Freeway") are left out: they are not necessarily vehicle incidents.
"""
import json
import urllib.parse
from datetime import datetime, timedelta, timezone

from .base import PACIFIC, coordinate, local_to_utc, utc_to_local

SOURCE = "seattle"
LABEL = "Seattle (Fire 911 dispatch)"
SNAPSHOT = False
URL = "https://cos-data.seattle.gov/resource/kzjm-xkqj.json"
BOUNDS = (47.08, -122.55, 47.79, -121.06)  # King County
PAGE = 50000
# Rows can land a few minutes after dispatch, so re-read a window before `since`.
OVERLAP = timedelta(hours=1)

CRASH_TYPES = (
    "MVI - Motor Vehicle Incident", "MVI Freeway", "MVI Medic", "MVI Freeway Medic",
    "Motor Vehicle Incident", "Motor Vehicle Incident Freeway",
    "Motor Vehicle Accident", "Motor Vehicle Accident Freeway",  # older code names for the same calls
    "Tunnel MVI", "Tunnel MVI Medic",
    "Rescue Extrication", "Tunnel Rescue Extrication", "Rescue Automobile",  # people trapped in vehicles
)
FIRE_TYPES = ("Car Fire", "Car Fire Freeway", "Car Fire W/Exp.", "Tunnel Car Fire", "RV Fire")
TYPES = {**{t: "crash" for t in CRASH_TYPES}, **{t: "fire" for t in FIRE_TYPES}}

def to_pacific(value: datetime) -> datetime:
    """Naive UTC -> naive Pacific local."""
    return utc_to_local(value, PACIFIC)


def from_pacific(value: datetime) -> datetime:
    """Naive Pacific local -> naive UTC."""
    return local_to_utc(value, PACIFIC)


def page_url(since: datetime | None, offset: int) -> str:
    quoted = ", ".join("'" + t.replace("'", "''") + "'" for t in TYPES)
    where = f"type in ({quoted})"
    if since:
        where += f" AND datetime >= '{to_pacific(since - OVERLAP):%Y-%m-%dT%H:%M:%S}'"
    params = {"$where": where, "$order": "datetime, incident_number", "$limit": str(PAGE), "$offset": str(offset)}
    return f"{URL}?{urllib.parse.urlencode(params)}"


def fetch(since, get) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = json.loads(get(page_url(since, offset)))
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def _reported(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo:  # not seen in this feed, but honour an explicit zone
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return from_pacific(parsed)


def parse(raw: dict) -> dict | None:
    source_id, reported = (raw.get("incident_number") or "").strip(), _reported(raw.get("datetime"))
    kind = (raw.get("type") or "").strip()
    if not source_id or reported is None or kind not in TYPES:
        return None
    lat, lon = coordinate(raw.get("latitude"), raw.get("longitude"), BOUNDS)
    return {
        "source_id": source_id,
        "category": TYPES[kind],
        "raw_type": kind,
        "description": "Seattle Fire Department 911 dispatch",
        "road": (raw.get("address") or "").strip() or None,
        "latitude": lat,
        "longitude": lon,
        "reported_at": reported,
        # The feed has no clear time or status: each row is a dispatch record, so updated_at is
        # the dispatch time (it is also what the poller resumes from) and every row is stored as
        # "cleared" rather than guessing how long a call stays active.
        "updated_at": reported,
        "status": "cleared",
    }
