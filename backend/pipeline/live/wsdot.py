"""Washington State DOT highway alerts (wsdot.wa.gov/Traffic/api/HighwayAlerts, no key needed).

Two public feeds list the same current alerts; checked Nov 2026 (110 alerts in each, same IDs):
- KML: one <Placemark id="ID 724659"> per alert with <name> (the alert text), <styleUrl> such as
  "#HighestCollision" (impact level Highest/High/Medium/Low/Lowest + event type, e.g. Collision,
  Disabledvehicle, Treesdown, Construction, Maintenance, LaneClosure, RestArea), and a
  <Point><coordinates>lon,lat</coordinates>. It carries no timestamps.
- RSS: <item> with <guid>724659</guid>, title/description (same text) and <a10:updated> with a
  Pacific offset, e.g. "2026-11-15T20:31:02-08:00". It carries no coordinates or event type.
So fetch() reads both and joins them on the alert ID: KML gives position and type, RSS gives time.
The feeds only give a last-updated time, so reported_at is that time (it moves when WSDOT edits
an alert). The feed lists active alerts only, hence SNAPSHOT = True.
"""
import html
import re
import xml.etree.ElementTree as ET

from .base import coordinate, utc

SOURCE = "wsdot"
LABEL = "Washington state highways (WSDOT alerts)"
SNAPSHOT = True
KML_URL = "https://wsdot.wa.gov/Traffic/api/HighwayAlerts/kml.aspx"
RSS_URL = "https://wsdot.wa.gov/Traffic/api/HighwayAlerts/rss.aspx"
BOUNDS = (45.5, -124.9, 49.1, -116.8)  # generous box around Washington
NS = {"kml": "http://www.opengis.net/kml/2.2", "a10": "http://www.w3.org/2005/Atom"}

_LEVEL = re.compile(r"^#?(Highest|High|Medium|Lowest|Low)(.*)$")
# Event types (style id without the impact level), lower-cased.
_TYPES = {
    "crash": {"collision", "collision-secondary", "collision-workzone", "collisionfatality", "multi-vehiclecollision",
              "rollover", "fatalityorpossiblefatality"},
    "stalled_vehicle": {"disabledvehicle", "abandonedvehicle", "derelictvehicle"},
    "closure": {"closure", "bridgeclosed", "emergencyclosure", "exitclosure", "passclosure", "rampclosure",
                "rocks-closure", "hcbclosedmaint", "hcbclosedmarine", "hcbclosedpolice", "hcbclosedwinds"},
    "hazard": {"debris", "debrisblocking", "deadanimal", "liveanimal", "trees", "treesdown", "rockslide", "rocks",
               "slide", "slides", "snowslide", "wateroverroadway", "weather", "weatherevent", "severesidewinds",
               "windadvisory", "powerlines", "pothole", "chemicalspill", "spill", "hazmat", "hazardousmaterial",
               "wrongwayvehicle", "pedestrian", "avalanchecontrol", "tractionadvisory", "chainenforcement"},
    "fire": {"fire", "brushfire", "vehiclefire"},
}
_PLANNED = {"construction", "maintenance", "roadwork", "laneclosure", "specialevent", "sand/plowing/deicing",
            "p-1sand/plowing/deicing", "bridge", "bridgelift", "shoulderoperations"}
_NEVER = {"restarea", "amberalert", "bluealert", "silveralert", "missingpersonalert", "missingindigenouspersonsalert",
          "hitandrunalert", "ferry", "fuelstation", "roadreopened", "workzonespeedcamera"}
# Generic types ("Incident", "Majorincident", "Other", ...) fall back to the alert text.
_TEXT_RULES = [
    (re.compile(r"COLLISION|CRASH|ROLLOVER", re.I), "crash"),
    (re.compile(r"FIRE", re.I), "fire"),
    (re.compile(r"DISABLED|STALLED", re.I), "stalled_vehicle"),
    (re.compile(r"DEBRIS|HAZARD|ANIMAL|TREES? DOWN|ROCKS?LIDE|FLOOD|WATER OVER", re.I), "hazard"),
]
_CLOSED = re.compile(r"\bclos(?:e|ed|es|ure|ures)\b", re.I)
_LANE = re.compile(r"\blanes?\b|\bshoulder\b", re.I)
_ALL_LANES = re.compile(r"\ball (?:travel )?lanes\b|\bfully clos", re.I)
_ROADS = [(re.compile(r"\b(?:I-?|Interstate\s+)(\d{1,3})\b"), "I-{}"),
          (re.compile(r"\b(?:SR|State Route)\s*(\d{1,3})\b"), "SR {}"),
          (re.compile(r"\bUS\s*(\d{1,3})\b"), "US {}")]


def plain(text: str | None) -> str | None:
    """Alert text without the HTML links WSDOT embeds, whitespace collapsed."""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text or "")).split())
    return text or None


def road_closed(text: str | None) -> bool:
    """True if a sentence says a road, ramp or bridge is closed (not just some of its lanes)."""
    # Split before a capital so "Nov. 16" and "7 a.m. to" stay in one sentence.
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text or ""):
        if _CLOSED.search(sentence) and (_ALL_LANES.search(sentence) or not _LANE.search(sentence)):
            return True
    return False


def event_type(style: str | None) -> str | None:
    """'#HighestCollision' -> 'Collision'."""
    match = _LEVEL.match((style or "").strip())
    return (match.group(2) if match else (style or "").lstrip("#")) or None


def category(style: str | None, text: str | None = None) -> str:
    kind = (event_type(style) or "").lower()
    for name, kinds in _TYPES.items():
        if kind in kinds:
            return name
    if kind in _NEVER:
        return "other"
    if kind in _PLANNED:
        return "closure" if road_closed(text) else "other"
    for pattern, name in _TEXT_RULES:
        if text and pattern.search(text):
            return name
    return "closure" if road_closed(text) else "other"


def road(text: str | None) -> str | None:
    """The first highway named in the text, normalised ('Interstate 90' -> 'I-90')."""
    found = [(m.start(), fmt.format(m.group(1))) for pattern, fmt in _ROADS for m in [pattern.search(text or "")] if m]
    return min(found)[1] if found else None


def _xml(body: str) -> ET.Element:
    return ET.fromstring(body.lstrip("﻿").strip())


def fetch(since, get) -> list[dict]:
    updated = {}
    for item in _xml(get(RSS_URL)).iterfind("./channel/item"):
        guid = (item.findtext("guid") or "").strip()
        if guid:
            updated[guid] = (item.findtext("a10:updated", namespaces=NS) or "").strip() or None
    rows = []
    for mark in _xml(get(KML_URL)).iterfind(".//kml:Placemark", NS):
        alert_id = (mark.get("id") or "").removeprefix("ID").strip()
        lon = lat = None
        coords = (mark.findtext("kml:Point/kml:coordinates", namespaces=NS) or "").split(",")
        if len(coords) >= 2:
            lon, lat = coords[0].strip(), coords[1].strip()
        rows.append({"id": alert_id, "style": mark.findtext("kml:styleUrl", namespaces=NS),
                     "text": mark.findtext("kml:name", namespaces=NS), "latitude": lat, "longitude": lon,
                     "updated": updated.get(alert_id)})
    return rows


def parse(raw: dict) -> dict | None:
    source_id, reported = (raw.get("id") or "").strip(), utc(raw.get("updated"))
    if not source_id or reported is None:
        return None
    text, style = plain(raw.get("text")), raw.get("style")
    lat, lon = coordinate(raw.get("latitude"), raw.get("longitude"), BOUNDS)
    level = _LEVEL.match((style or "").strip())
    return {
        "source_id": source_id,
        "category": category(style, text),
        "raw_type": event_type(style),
        "description": f"{level.group(1)} impact: {text}" if level and text else text,
        "road": road(text),
        "latitude": lat,
        "longitude": lon,
        "reported_at": reported,
        "updated_at": reported,
        "status": "active",
    }
