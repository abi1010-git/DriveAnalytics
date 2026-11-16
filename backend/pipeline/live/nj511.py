"""511NJ / TRANSCOM "Active Incidents" RSS (https://511nj.org/client/rest/rss/RSSActiveIncidents).

A keyless RSS 2.0 snapshot of every currently active incident TRANSCOM relays: NJ agencies
(NJ DOT, NJ Turnpike, Port Authority) plus New York ones (NYSDOT regions, NYS Thruway), so
items reach upstate NY. Checked Nov 2026:
- items carry only title, description, pubDate (RFC 822 with offset, e.g. -0500) and
  georss:point ("lat lon"); there is no guid or id element
- title is "<road> <direction> : <event type>", e.g. "I-90 - NYS Thruway eastbound : Crash",
  "I-684 southbound : Disabled vehicle", "I-287 northbound : Fuel spill"
- description is "<agency>: <event> on <road> ...", sometimes ending in a CAD number such as
  "[CARS CAD-263200008]" or "CAD #98050080"
- feed is small (about 10 items) and mixes in roadwork, roving repairs, truck restrictions
The sibling RSSAllNJActiveEvents feed (about 800 items) is almost all planned roadwork and
stadium events; in the same snapshot its only incident also appeared here, so it adds noise,
not crashes, and is not used.
"""
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

from .base import coordinate

SOURCE = "nj511"
LABEL = "New Jersey & New York region (511NJ / TRANSCOM)"
SNAPSHOT = True
URL = "https://511nj.org/client/rest/rss/RSSActiveIncidents"
BOUNDS = (38.8, -80.6, 45.1, -71.7)  # box around NJ, NY, CT and PA
GEORSS = "{http://www.georss.org/georss}point"

_RULES = [
    (re.compile(r"CRASH|ACCIDENT|COLLISION", re.I), "crash"),
    (re.compile(r"\bFIRE\b", re.I), "fire"),
    (re.compile(r"DISABLED|STALLED", re.I), "stalled_vehicle"),
    (re.compile(r"DEBRIS|HAZARD|FLOOD|ANIMAL|SPILL", re.I), "hazard"),
    (re.compile(r"CLOSURE|CLOSED", re.I), "closure"),
]
_DIRECTION = re.compile(r"\s+(north|south|east|west)bound$|\s+both directions$", re.I)
_CAD = re.compile(r"CAD[\s#-]*(\d{5,})", re.I)


def category(text: str | None) -> str:
    for pattern, name in _RULES:
        if text and pattern.search(text):
            return name
    return "other"


def _split_title(title: str) -> tuple[str | None, str | None]:
    """"I-87 - NYS Thruway northbound : Crash" -> ("I-87 - NYS Thruway", "Crash")."""
    road, sep, event = title.rpartition(" : ")
    if not sep:
        return None, title.strip() or None
    road = _DIRECTION.sub("", road.strip()).strip()
    return road or None, event.strip() or None


def _lead(description: str) -> str:
    """The event phrase of a description: "NYSTA - Statewide Ops.: crash ,left lane blocked on
    I-90 ..." -> "crash ,left lane blocked". Classifying on this rather than the whole text keeps
    words in place names ("Fire Island") or lane notes ("right shoulder closed") from counting."""
    body = description.split(": ", 1)[-1]
    return re.split(r"\s+(?:on|at)\s+", body, maxsplit=1)[0]


def classify(title: str | None, description: str | None) -> str:
    """Event type from the title wins; if it says nothing useful, try the description's lead.
    Closures only come from the title, since descriptions of roadwork mention closed lanes."""
    _, event = _split_title(title or "")
    found = category(event)
    if found == "other" and description:
        found = category(_lead(description))
        if found == "closure":
            found = "other"
    return found


def _reported(value: str | None):
    try:
        parsed = parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def source_id(title: str, description: str, point: str | None, pub_date: str | None) -> str:
    """The feed has no id, and the poller clears any id missing from the latest snapshot, so the
    id must survive an incident being updated. Agencies edit the description (lanes blocked,
    lanes reopened) far more than anything else, so it is left out.
    - When the description carries a CAD number, that is the agency's own incident number: use it.
    - Otherwise hash the normalized title + point rounded to ~100 m + pubDate. pubDate looks like
      the incident's start time (it matches the "starting ..." time in NYSTA descriptions), which
      separates a new incident at the same spot from an old one. Trade-off: if an agency re-stamps
      pubDate or nudges the point on update, that incident gets a new id, so the old row is marked
      cleared and a new one inserted (a duplicate in history, never a missing incident)."""
    cad = _CAD.search(description or "")
    if cad:
        return f"cad-{cad.group(1)}"
    try:
        lat, lon = (round(float(v), 3) for v in (point or "").split()[:2])
        where = f"{lat:.3f},{lon:.3f}"
    except ValueError:
        where = ""
    key = "|".join((re.sub(r"\s+", " ", title).strip().lower(), where, (pub_date or "").strip()))
    return "h-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _text(item: ET.Element, tag: str) -> str | None:
    value = item.findtext(tag)
    return value.strip() if value and value.strip() else None


def fetch(since, get) -> list[dict]:
    body = get(URL)
    if "<!DOCTYPE" in body or "<!ENTITY" in body:
        raise ValueError("unexpected DTD in 511NJ feed")  # plain RSS never needs one
    root = ET.fromstring(body)
    return [{"title": _text(item, "title"), "description": _text(item, "description"),
             "pubDate": _text(item, "pubDate"), "point": _text(item, GEORSS)}
            for item in root.iter("item")]


def parse(raw: dict) -> dict | None:
    title, description = raw.get("title"), raw.get("description")
    reported = _reported(raw.get("pubDate"))
    if not title or reported is None:
        return None
    road, event = _split_title(title)
    parts = (raw.get("point") or "").split()
    lat, lon = coordinate(*(parts[:2] if len(parts) >= 2 else (None, None)), BOUNDS)
    return {
        "source_id": source_id(title, description or "", raw.get("point"), raw.get("pubDate")),
        "category": classify(title, description),
        "raw_type": event,
        "description": description,
        "road": road,
        "latitude": lat,
        "longitude": lon,
        "reported_at": reported,
        "updated_at": None,
        "status": "active",
    }
