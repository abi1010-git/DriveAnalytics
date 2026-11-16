"""Austin-Travis County "Real-Time Traffic Incident Reports" (data.austintexas.gov, dx9v-zd7x).

Fed from the Combined Transportation, Emergency & Communications Center (CTECC); published
"Multiple Per Day" and in practice within about 30-40 minutes. Checked Nov 2026:
- fields: traffic_report_id, published_date, issue_reported, latitude, longitude, address,
  traffic_report_status (ACTIVE / ARCHIVED), traffic_report_status_date_time, agency
- timestamps end in "Z" (UTC)
- issue_reported is free text from several agencies, e.g. "Crash Urgent", "COLLISION",
  "COLLISN/ LVNG SCN", "AUTO/ PED", "Traffic Hazard", "zSTALLED VEHICLE"
"""
import re
import urllib.parse
from datetime import datetime, timedelta

from .base import coordinate, utc

SOURCE = "austin"
LABEL = "Austin & Travis County, TX"
SNAPSHOT = False
URL = "https://data.austintexas.gov/resource/dx9v-zd7x.json"
BOUNDS = (29.9, -98.3, 30.75, -97.2)  # generous box around Travis County
PAGE = 5000
# Records are updated after publication (status changes), so re-read a window before `since`.
OVERLAP = timedelta(hours=2)

_RULES = [
    (re.compile(r"CRASH|COLLIS|COLLISN|AUTO/ ?PED|VEH(ICLE)?/ ?PED", re.I), "crash"),
    (re.compile(r"FIRE", re.I), "fire"),
    (re.compile(r"STALL", re.I), "stalled_vehicle"),
    (re.compile(r"BLOCKED|CLOSURE|CLOSED", re.I), "closure"),
    (re.compile(r"HAZ|DEBRIS|IMPEDIMENT|LIVESTOCK|ANIMAL", re.I), "hazard"),
]


def category(issue: str | None) -> str:
    for pattern, name in _RULES:
        if issue and pattern.search(issue):
            return name
    return "other"


def page_url(since: datetime | None, offset: int) -> str:
    params = {"$order": "traffic_report_status_date_time, traffic_report_id", "$limit": str(PAGE), "$offset": str(offset)}
    if since:
        stamp = (since - OVERLAP).strftime("%Y-%m-%dT%H:%M:%S")
        params["$where"] = f"traffic_report_status_date_time >= '{stamp}' OR published_date >= '{stamp}'"
    return f"{URL}?{urllib.parse.urlencode(params)}"


def fetch(since, get_json) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = get_json(page_url(since, offset))
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def parse(raw: dict) -> dict | None:
    source_id, reported = raw.get("traffic_report_id"), utc(raw.get("published_date"))
    if not source_id or reported is None:
        return None
    lat, lon = coordinate(raw.get("latitude"), raw.get("longitude"), BOUNDS)
    issue = (raw.get("issue_reported") or "").strip() or None
    status = (raw.get("traffic_report_status") or "").upper()
    return {
        "source_id": source_id,
        "category": category(issue),
        "raw_type": issue,
        "description": f"Reported by {raw['agency'].strip()}" if raw.get("agency") else None,
        "road": (raw.get("address") or "").strip() or None,
        "latitude": lat,
        "longitude": lon,
        "reported_at": reported,
        "updated_at": utc(raw.get("traffic_report_status_date_time")),
        "status": "cleared" if status == "ARCHIVED" else "active",
    }
