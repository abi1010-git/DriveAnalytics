"""San Francisco "Law Enforcement Dispatched Calls for Service: Real-Time" (data.sf.gov, gnap-fj3t).

SFPD calls dispatched by the Department of Emergency Management, public domain (PDDL). The
dataset is a rolling window: rows stay while call_last_updated_at is within about the last
48 hours, then roll off, so the feed is incremental and rows that disappear are kept as history.
Checked Nov 2026:
- fields: id, cad_number (one row per call; both unique in the window), received_datetime,
  close_datetime, call_last_updated_at, call_type_final(_desc), disposition, priority_final,
  intersection_name, intersection_point (GeoJSON Point at the nearest intersection),
  police_district, sensitive_call (sensitive calls carry no location)
- timestamps are Pacific local time with no zone, e.g. "2026-11-15T19:33:50.000"
- traffic call types: 518 VEH ACCIDENT, 518HR H&R VEH ACCIDENT, 519 INJURY VEH ACCIDENT,
  519HR H&R INJURY ACCIDENT (518HRL also seen as an original type), 586 TRAFFIC HAZARD.
  No stalled or blocked-vehicle type appears; 585/587/588 are enforcement stops, not incidents.
"""
import json
import urllib.parse
from datetime import datetime, timedelta

from .base import PACIFIC, coordinate, local_to_utc, utc_to_local

SOURCE = "sf"
LABEL = "San Francisco (police dispatch)"
SNAPSHOT = False
URL = "https://data.sf.gov/resource/gnap-fj3t.json"
BOUNDS = (37.6, -122.55, 37.85, -122.35)  # the city and county, Treasure Island included
PAGE = 5000
# Calls are updated after they are received (dispatch, close), so re-read a window before `since`.
OVERLAP = timedelta(hours=2)

# 518/519 and their hit-and-run variants (518HR, 518HRL, 519HR...) are collisions; 586 is a hazard.
WHERE_TYPES = "(call_type_final like '518%' OR call_type_final like '519%' OR call_type_final = '586')"

def pacific_to_utc(value: str | None) -> datetime | None:
    """Naive Pacific local timestamp -> naive UTC."""
    if not value:
        return None
    try:
        local = datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None
    return local_to_utc(local, PACIFIC)


def utc_to_pacific(value: datetime) -> datetime:
    """Naive UTC -> naive Pacific local (for building the query)."""
    return utc_to_local(value, PACIFIC)


def category(call_type: str | None) -> str:
    code = (call_type or "").strip().upper()
    if code.startswith(("518", "519")):
        return "crash"
    if code == "586":
        return "hazard"
    return "other"


def page_url(since: datetime | None, offset: int) -> str:
    params = {"$order": "call_last_updated_at, id", "$limit": str(PAGE), "$offset": str(offset), "$where": WHERE_TYPES}
    if since:
        stamp = utc_to_pacific(since - OVERLAP).strftime("%Y-%m-%dT%H:%M:%S")
        params["$where"] += f" AND (call_last_updated_at >= '{stamp}' OR received_datetime >= '{stamp}')"
    return f"{URL}?{urllib.parse.urlencode(params)}"


def fetch(since, get) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = json.loads(get(page_url(since, offset)))
        rows.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    # One row per call is expected; if a call ever repeats (paging shifts, per-unit rows), keep its latest copy.
    latest = {}
    for row in rows:
        key = row.get("cad_number") or row.get("id")
        if key not in latest or (row.get("call_last_updated_at") or "") >= (latest[key].get("call_last_updated_at") or ""):
            latest[key] = row
    return list(latest.values())


def parse(raw: dict) -> dict | None:
    source_id, reported = raw.get("cad_number") or raw.get("id"), pacific_to_utc(raw.get("received_datetime"))
    if not source_id or reported is None:
        return None
    point = raw.get("intersection_point") or {}
    lon, lat = (point.get("coordinates") or [None, None])[:2] if isinstance(point, dict) else (None, None)
    lat, lon = coordinate(lat, lon, BOUNDS)
    code = (raw.get("call_type_final") or "").strip()
    desc = (raw.get("call_type_final_desc") or "").strip()
    closed = pacific_to_utc(raw.get("close_datetime"))
    updated = max((t for t in (reported, closed, pacific_to_utc(raw.get("call_last_updated_at"))) if t), default=None)
    details = [f"Priority {raw['priority_final']}" if raw.get("priority_final") else None,
               f"{raw['police_district'].title()} district" if raw.get("police_district") else None,
               f"disposition {raw['disposition']}" if raw.get("disposition") else None]
    road = (raw.get("intersection_name") or "").replace("\\", "&").strip()
    return {
        "source_id": str(source_id),
        "category": category(code),
        "raw_type": f"{code} {desc}".strip() or None,
        "description": ", ".join(d for d in details if d) or None,
        "road": " ".join(road.split()) or None,
        "latitude": lat,
        "longitude": lon,
        "reported_at": reported,
        "updated_at": updated,
        "status": "cleared" if closed or raw.get("disposition") else "active",
    }
