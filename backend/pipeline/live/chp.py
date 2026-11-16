"""California Highway Patrol CAD incident feed (media.chp.ca.gov/sa_xml/sa.xml).

The public "CHP Traffic Incident Information" XML: every incident currently open in CHP's
dispatch system, statewide, refreshed about every minute. No key. Checked Nov 2026:
- layout: <State><Center ID="SAHB"><Dispatch ID="SACC"><Log ID="261115SA0875">...; log IDs
  embed the date and a two-letter code that does not always match the dispatch (YKCC uses
  "RD"), so the dispatch ID is prefixed to make them unique beyond doubt
- every element value is wrapped in literal double quotes, e.g. <Area>"Auburn"</Area>
- LogTime/DetailTime/UnitTime are Pacific local time without a zone, "Nov 15 2026  9:49PM"
- LATLON is "38918480:121081135" = lat*1e6 : -lon*1e6 (longitude sign dropped); "0:0" when unknown
- LogType, e.g. "1182-Trfc Collision-No Inj", "1179-Trfc Collision-1141 Enrt",
  "20002-Hit and Run No Injuries", "1125-Traffic Hazard", "1125A-Animal Hazard",
  "CLOSURE of a Road", "CFIRE-Car Fire", "FLOOD-Roadway Flooding", "SPINOUT",
  "CZP-Assist with Construction", "FOG-Foggy Conditions", "SILVER-Missing Elderly"
- Location is the road/intersection ("Us50 W / Shingle Springs Dr"), LocationDesc a free-text
  landmark ("WB 50 AT SHINGLE SPRINGS"), Area the CHP area office ("Placerville")
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

from .base import PACIFIC, coordinate, local_to_utc

SOURCE = "chp"
LABEL = "California (CHP incidents, statewide)"
SNAPSHOT = True
URL = "https://media.chp.ca.gov/sa_xml/sa.xml"
BOUNDS = (32.4, -124.6, 42.1, -114.1)  # California plus a small margin

_RULES = [
    (re.compile(r"COLLISION|HIT AND RUN|\bTC\b", re.I), "crash"),
    (re.compile(r"FIRE", re.I), "fire"),
    (re.compile(r"STALL|DISABLED", re.I), "stalled_vehicle"),
    (re.compile(r"CLOSURE|CLOSED", re.I), "closure"),
    (re.compile(r"HAZARD|DEBRIS|ANIMAL|LIVESTOCK|FLOOD|SPINOUT", re.I), "hazard"),
]

def category(log_type: str | None) -> str:
    for pattern, name in _RULES:
        if log_type and pattern.search(log_type):
            return name
    return "other"


def pacific_to_utc(local: datetime) -> datetime:
    """Naive Pacific wall-clock time -> naive UTC."""
    return local_to_utc(local, PACIFIC)


def _clean(value: str | None) -> str | None:
    value = (value or "").strip().strip('"').strip()
    return value or None


def parse_time(value: str | None) -> datetime | None:
    """'Nov 15 2026  9:49PM' (Pacific) -> naive UTC."""
    if not value:
        return None
    try:
        local = datetime.strptime(" ".join(value.split()), "%b %d %Y %I:%M%p")
    except ValueError:
        return None
    return pacific_to_utc(local)


def latlon(value: str | None) -> tuple[float | None, float | None]:
    try:
        lat, lon = value.split(":")
        return int(lat) / 1e6, -abs(int(lon)) / 1e6
    except (AttributeError, ValueError):
        return None, None


def records(xml_text: str) -> list[dict]:
    """Flatten the XML into one plain dict per <Log>. Values are kept as text."""
    root = ET.fromstring(xml_text)
    rows = []
    for center in root.iter("Center"):
        for dispatch in center.iter("Dispatch"):
            for log in dispatch.iter("Log"):
                rows.append({
                    "center": center.get("ID"), "dispatch": dispatch.get("ID"), "log_id": log.get("ID"),
                    **{tag: _clean(log.findtext(tag)) for tag in ("LogTime", "LogType", "Location", "LocationDesc", "Area", "LATLON")},
                    "detail_times": [_clean(e.text) for tag in ("DetailTime", "UnitTime") for e in log.iter(tag) if _clean(e.text)],
                })
    return rows


RETRY_DELAY = 5  # seconds


def fetch(since, get) -> list[dict]:
    """CHP rewrites sa.xml in place, so a request can catch it half-written (seen on ~6 in 10
    polls on Nov 16, 2026: "unclosed token"). Retry a few times; a truncated file must never be
    parsed partially, because as a snapshot feed that would mark the missing incidents cleared."""
    for attempt in range(3):
        try:
            return records(get(URL))
        except ET.ParseError:
            if attempt == 2:
                raise
            time.sleep(RETRY_DELAY * (attempt + 1))


def parse(raw: dict) -> dict | None:
    log_id, reported = raw.get("log_id"), parse_time(raw.get("LogTime"))
    if not log_id or reported is None:
        return None
    lat, lon = coordinate(*latlon(raw.get("LATLON")), BOUNDS)
    updates = [t for t in (parse_time(v) for v in raw.get("detail_times") or []) if t and t > reported]
    log_type = raw.get("LogType")
    description = " - ".join(part for part in (raw.get("LocationDesc"), raw.get("Area")) if part) or None
    return {
        "source_id": f"{raw.get('dispatch') or raw.get('center') or 'CHP'}-{log_id}",
        "category": category(log_type),
        "raw_type": log_type,
        "description": description,
        "road": raw.get("Location"),
        "latitude": lat,
        "longitude": lon,
        "reported_at": reported,
        "updated_at": max(updates) if updates else None,
        "status": "active",
    }
