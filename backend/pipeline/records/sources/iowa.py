"""Iowa DOT statewide crashes (ArcGIS Traffic_Safety/Crash_Data/FeatureServer/0).

Checked Nov 2026: 641,341 rows, 2015-01-01 00:13 to 2026-11-12 17:11, refreshed every few
days (REST_UPDATED). One row per crash, but 953 CRASH_KEY values (crashes from Apr 2025 to
May 2026) appear twice as identical rows apart from OBJECTID; the loader's per-id collapse
keeps one, so no `reduce` is needed. Every row has a point. No license or terms are stated
on the service (copyrightText empty).

Time: CRASH_DATETIME is local wall time stored "as UTC" (epoch_is_local=True). Evidence:
CRASH_DATE is always 00:00 UTC, and for 1,000 rows (Jul-Nov 2026 and Jan 2019, i.e. both
DST and standard time) the UTC clock of CRASH_DATETIME matched the text field TIMESTR
exactly; CRASH_DATETIME_UTC is empty. The loader's TIMESTAMP filter therefore compares
local to local, and works on this server.

Fields: CSEV, LIGHT, WEATHER, CRCOMNNR (manner of collision) and MAJCSE (major cause) are
integer codes; the labels below are the service's own coded-value domains. injured is the
sum of MAJINJURY, MININJURY, POSSINJURY and UNKINJURY (equal to INJURIES in all 1,000 rows
checked); killed is FATALITIES. road is the route (SYSTEMSTR, e.g. "I-80") when there is
one; SYSTEMSTR "77" (381k rows, local streets) is not a route, so LITERAL, the officer's
location text (e.g. "SCOTT AVE AND SE 10TH ST"), is used instead. There is no hit-and-run
field. "Not Reported" codes (77) are left empty.
"""
from ..base import SourceSpec, epoch, number, point, sane, text

SEVERITY = {1: "Fatal", 2: "Major Injury", 3: "Minor Injury", 4: "Possible/Unknown", 5: "Property Damage Only"}
LIGHT = {1: "Daylight", 2: "Dusk", 3: "Dawn", 4: "Dark - roadway lighted", 5: "Dark - roadway not lighted",
         6: "Dark - unknown roadway lighting", 9: "Unknown"}
WEATHER = {1: "Clear", 2: "Cloudy", 3: "Fog, smoke, smog", 4: "Freezing rain/drizzle", 5: "Rain", 6: "Sleet, hail",
           7: "Snow", 8: "Blowing Snow", 9: "Severe Winds", 10: "Blowing sand, soil, dirt",
           98: "Other (explain in narrative)", 99: "Unknown"}
MANNER = {1: "Non-collision (single vehicle)", 2: "Head-on (front to front)", 3: "Rear-end (front to rear)",
          4: "Angle, oncoming left turn", 5: "Broadside (front to side)", 6: "Sideswipe, same direction",
          7: "Sideswipe, opposite direction", 8: "Rear to rear", 9: "Rear to side", 98: "Other (explain in narrative)",
          99: "Unknown"}
CAUSE = {
    1: "Animal", 2: "Ran Traffic Signal", 3: "Ran Stop Sign", 4: "Failed to yield to emergency vehicle",
    5: "FTYROW: At uncontrolled intersection", 6: "FTYROW: Making right turn on red signal",
    7: "FTYROW: From stop sign", 8: "FTYROW: From yield sign", 9: "FTYROW: Making left turn",
    10: "FTYROW: From driveway", 11: "FTYROW: From parked position", 12: "FTYROW: To pedestrian",
    13: "FTYROW: Other (explain in narrative)", 14: "Drove around RR grade crossing gates",
    15: "Disregarded RR Signal", 16: "Crossed centerline (undivided)", 17: "Crossed median (divided)",
    18: "Traveling wrong way or on wrong side of road", 19: "Aggressive driving/road rage",
    20: "Driving too fast for conditions", 21: "Exceeded authorized speed", 22: "Improper or erratic lane changing",
    23: "Operating vehicle in an reckless, erratic, careless, negligent manner", 24: "Followed too close",
    25: "Passing: On wrong side", 26: "Passing: Where prohibited by signs/markings",
    27: "Passing: With insufficient distance/inadequate visibility", 28: "Passing: Through/around barrier",
    29: "Passing: Other passing (explain in narrative)", 30: "Made improper turn",
    31: "Driver Distraction: Manual operation of an electronic communication device",
    32: "Driver Distraction: Talking on a hand-held device", 33: "Driver Distraction: Talking on a hands free device",
    34: "Driver Distraction: Adjusting devices (radio, climate)",
    35: "Driver Distraction: Other electronic device activity", 36: "Driver Distraction: Passenger",
    37: "Driver Distraction: Unrestrained animal", 38: "Driver Distraction: Reaching for object(s)/fallen object(s)",
    39: "Driver Distraction: Inattentive/lost in thought", 40: "Driver Distraction: Other interior distraction",
    41: "Driver Distraction: Exterior distraction", 42: "Lost Control", 43: "Ran off road - right",
    44: "Ran off road - straight", 45: "Ran off road - left", 46: "Swerving/Evasive Action",
    47: "Over correcting/over steering", 48: "Failed to keep in proper lane", 49: "Failure to signal intentions",
    50: "Traveling on prohibited traffic way", 51: "Vehicle stopped on railroad tracks",
    52: "Other (explain in narrative): Vision obstructed", 53: "Other (explain in narrative): Improper operation",
    54: "Other (explain in narrative): Disregarded Warning Sign",
    55: "Other (explain in narrative): Disregarded signs/road markings",
    56: "Other (explain in narrative): Illegal off-road driving", 57: "Downhill runaway", 58: "Separation of units",
    59: "Towing Improperly", 60: "Cargo/equipment loss or shift", 61: "Equipment failure",
    62: "Oversized Load/Vehicle", 63: "Other (explain in narrative): Getting off/out of vehicle",
    64: "Failure to dim lights/have lights on", 65: "Improper Backing", 66: "Improper Starting",
    67: "Illegally Parked/Unattended", 68: "Driving less than the posted speed limit", 69: "Operator inexperience",
    70: "Other (explain in narrative): Other", 71: "Unknown",
    73: "Other (explain in narrative): No improper action", 99: "Unknown",
}
INJURY_COUNTS = ("MAJINJURY", "MININJURY", "POSSINJURY", "UNKINJURY")


def _label(table: dict, value) -> str | None:
    code = number(value)
    return table.get(code) if code is not None else None


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in INJURY_COUNTS]
    if all(c is None for c in counts):
        return number(raw.get("INJURIES"))
    return sum(c or 0 for c in counts)


def _road(raw: dict) -> str | None:
    route = text(raw.get("SYSTEMSTR"))
    return route if route and route != "77" else text(raw.get("LITERAL"))


def parse(raw: dict) -> dict | None:
    key = number(raw.get("CRASH_KEY"))
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(key) if key else None,
        "crash_datetime": sane(epoch(SPEC, raw.get("CRASH_DATETIME"))),
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": _injured(raw),
        "killed": number(raw.get("FATALITIES")),
        "severity": _label(SEVERITY, raw.get("CSEV")),
        "primary_cause": _label(CAUSE, raw.get("MAJCSE")),
        "weather": _label(WEATHER, raw.get("WEATHER")),
        "lighting": _label(LIGHT, raw.get("LIGHT")),
        "crash_type": _label(MANNER, raw.get("CRCOMNNR")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="iowa",
    label="Iowa DOT crash reports",
    platform="arcgis",
    url="https://gis.iowadot.gov/agshost/rest/services/Traffic_Safety/Crash_Data/FeatureServer/0",
    date_field="CRASH_DATETIME",
    parse=parse,
    states=[19],
    bbox=(-96.8, 40.3, -90.0, 43.6),
    tz="America/Chicago",
    page_size=2000,
    epoch_is_local=True,
    notes="Statewide from 2015 (about 641k crashes). No hit-and-run field.",
)
