"""MDT "MT Public Crash Information" (ArcGIS MapServer MDTGIS/Public_Crash_Information, layer 0),
statewide, published as yearly snapshots (no current-year data).

Checked Nov 2026: 219,418 rows from 2016-01-01 to 2025-12-31 (about 20,300-23,700 a year);
this source loads 2021 onward: 107,131 rows. Every row has a point. maxRecordCount 2000. The
service carries only 12 attributes: ROUTE_ID, RP (reference point), CITY_NAME, COUNTY,
CRASH_DATE, COL_TYPE, CRASH_SEVERITY, WEATHER, SURF_COND, LIGHT_COND and X/Y_COORD (Montana
State Plane, EPSG:32100, metres); the loader asks for the geometry in WGS84 (outSR=4326). Re-read monthly
(refresh_days=30), as it changes only when a new year is published. No
license is stated; copyright text "Montana Department of Transportation".

Id: there is no crash, report or case number in any field, and OBJECTID is not stable when the
layer is republished. The id is built from the fields that describe where and when the crash
happened: CRASH_DATE + X/Y_COORD rounded to 1 cm + ROUTE_ID + RP + COL_TYPE, hashed. On the
2021+ rows this gives 106,980 ids for 107,131 rows: 151 rows (0.14%) share an id with
another row, 75 of them identical in every attribute (likely true duplicates, but two
same-day crashes at one spot cannot be told apart), so counts can be slightly low. Severity,
weather and surface are left out of the id so a later correction to them updates the row;
a corrected date, position or collision type would load it as a new crash.

Time: CRASH_DATE is esriFieldTypeDateOnly, returned as a "YYYY-MM-DD" string, parsed here to
local midnight (no time of day). The loader's TIMESTAMP filter works on it, as does DATE.

Fields: severity = CRASH_SEVERITY (KABCO wording, e.g. "Suspected Serious Injury"). No injury
or death counts, road names, cause or hit-and-run fields are published, so those stay empty.
"""
import hashlib
from datetime import date, datetime

from ..base import SourceSpec, point, sane, text


def _day(value) -> datetime | None:
    try:
        day = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
    return datetime(day.year, day.month, day.day)


def _id(raw: dict) -> str | None:
    day, x, y = raw.get("CRASH_DATE"), raw.get("X_COORD"), raw.get("Y_COORD")
    if not day or x is None or y is None:
        return None
    try:
        parts = [str(day)[:10], f"{float(x):.2f}", f"{float(y):.2f}"]
    except (TypeError, ValueError):
        return None
    parts += [text(raw.get(k)) or "" for k in ("ROUTE_ID", "RP", "COL_TYPE")]
    return f"{parts[0]}-{hashlib.sha1('|'.join(parts).encode()).hexdigest()[:16]}"


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": _id(raw),
        "crash_datetime": sane(_day(raw.get("CRASH_DATE"))),
        "latitude": lat,
        "longitude": lon,
        "road": None,
        "injured": None,
        "killed": None,
        "severity": text(raw.get("CRASH_SEVERITY")),
        "primary_cause": None,
        "weather": text(raw.get("WEATHER")),
        "lighting": text(raw.get("LIGHT_COND")),
        "crash_type": text(raw.get("COL_TYPE")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="montana",
    label="Montana DOT crash reports (statewide, 2021-2025)",
    platform="arcgis",
    url="https://gis.mtmdt.us/server/rest/services/MDTGIS/Public_Crash_Information/MapServer/0",
    date_field="CRASH_DATE",
    where="CRASH_DATE >= DATE '2021-01-01'",
    parse=parse,
    states=[30],
    bbox=(-116.1, 44.3, -104.0, 49.05),
    tz="America/Denver",
    page_size=2000,
    refresh_days=30,
    notes="Statewide from 2021 through the last published year (2025 when checked); date only. No crash id is "
          "published, so ids are built from date, position, route and collision type (0.14% of rows collapse). "
          "Severity label only, no injury or death counts.",
)
