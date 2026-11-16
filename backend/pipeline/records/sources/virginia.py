"""VDOT "Full_Crash" CrashData_Basic (ArcGIS Full_Crash/FeatureServer/0).

Checked Nov 2026: 1,175,583 rows from 2017-01-01 to 2026-08-31 (published about 2.5 months
behind; 2025 is complete at 115,858 crashes). One row per crash: DOCUMENT_NBR is unique
(1,175,583 distinct). 61 rows have no LAT/LON. Copyright "VDOT"; no license terms stated.

Load window: `where` starts at 2019-01-01, which keeps 916,360 rows and drops 2017-2018.
CRASH_DT >= TIMESTAMP '2019-01-01 00:00:00' compares in UTC, and the first 2019 value is
05:00 UTC, so all of local 2019 is included.

Time: CRASH_DT holds only the date, as true UTC of local midnight (04:00 or 05:00 UTC
depending on DST; all 4,000 rows sampled from 2019 and 2026 converted to exactly 00:00
America/New_York), so epoch_is_local stays False. The clock time is the separate
CRASH_MILITARY_TM (HHMM, 0..2359, all valid in the sample), added to that date.

Fields: severity, collision type, weather and light are codes; labels are the service's
coded-value domains without their "A. " / "1. " ordering prefix, and "Not Provided" /
"Not Applicable" stay empty. injured = A + B + C people (equal to PERSONS_INJURED in every
row sampled); killed = K_PEOPLE. road is ROUTE_OR_STREET_NM, falling back to the linear
route id RTE_NM. There is no primary-cause field (only yes/no flags).
"""
from datetime import timedelta

from ..base import SourceSpec, epoch, number, point, sane, text

SEVERITY = {"K": "Fatal Injury", "A": "Severe Injury", "B": "Visible Injury", "C": "Nonvisible Injury",
            "O": "Property Damage Only"}
COLLISION = {"1": "Rear End", "2": "Angle", "3": "Head On", "4": "Sideswipe - Same Direction",
             "5": "Sideswipe - Opposite Direction", "6": "Fixed Object in Road", "7": "Train", "8": "Non-Collision",
             "9": "Fixed Object - Off Road", "10": "Deer", "11": "Other Animal", "12": "Ped", "13": "Bicyclist",
             "14": "Motorcyclist", "15": "Backed Into", "16": "Other"}
WEATHER = {"1": "No Adverse Condition (Clear/Cloudy)", "3": "Fog", "4": "Mist", "5": "Rain", "6": "Snow",
           "7": "Sleet/Hail", "8": "Smoke/Dust", "9": "Other", "10": "Blowing Sand, Soil, Dirt, or Snow",
           "11": "Severe Crosswinds"}
LIGHT = {"1": "Dawn", "2": "Daylight", "3": "Dusk", "4": "Darkness - Road Lighted", "5": "Darkness - Road Not Lighted",
         "6": "Darkness - Unknown Road Lighting", "7": "Unknown"}
HIT_RUN = {"1": True, "0": False}


def _when(raw: dict):
    day = epoch(SPEC, raw.get("CRASH_DT"))
    clock = number(raw.get("CRASH_MILITARY_TM"))
    if day is None:
        return None
    if clock is None or clock > 2359 or clock % 100 > 59:
        return day  # date only
    return day + timedelta(hours=clock // 100, minutes=clock % 100)


def _code(table: dict, value) -> str | None:
    return table.get(str(value).strip()) if value is not None else None


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in ("A_PEOPLE", "B_PEOPLE", "C_PEOPLE")]
    if all(c is None for c in counts):
        return number(raw.get("PERSONS_INJURED"))
    return sum(c or 0 for c in counts)


def parse(raw: dict) -> dict | None:
    doc = number(raw.get("DOCUMENT_NBR"))
    lat, lon = point(SPEC, raw.get("LAT"), raw.get("LON"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(doc) if doc else None,
        "crash_datetime": sane(_when(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("ROUTE_OR_STREET_NM")) or text(raw.get("RTE_NM")),
        "injured": _injured(raw),
        "killed": number(raw.get("K_PEOPLE")),
        "severity": _code(SEVERITY, raw.get("CRASH_SEVERITY")),
        "primary_cause": None,
        "weather": _code(WEATHER, raw.get("WEATHER_CONDITION")),
        "lighting": _code(LIGHT, raw.get("LIGHT_CONDITION")),
        "crash_type": _code(COLLISION, raw.get("COLLISION_TYPE")),
        "hit_and_run": _code(HIT_RUN, raw.get("HITRUN_NOT_HITRUN")),
    }


SPEC = SourceSpec(
    source="virginia",
    label="Virginia DOT crash reports",
    platform="arcgis",
    url="https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/Full_Crash/FeatureServer/0",
    date_field="CRASH_DT",
    parse=parse,
    states=[51],
    bbox=(-83.8, 36.4, -75.1, 39.6),
    tz="America/New_York",
    where="CRASH_DT >= TIMESTAMP '2019-01-01 00:00:00'",
    page_size=2000,
    notes="Statewide from 2019-01-01 (the service goes back to 2017; about 916k crashes loaded). "
          "Published about 2.5 months behind. No primary-cause field.",
)
