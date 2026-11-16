"""Dallas County, TX "2025 traffic accidents_no duplicates" (ArcGIS item 80a749259da5420d978832dda215831c),
a county GIS extract of TxDOT CRIS crash records for calendar year 2025 only.

Checked Nov 2026: 47,628 rows, 2025-01-01 to 2025-12-31, last modified 2026-03-30 (static; no
further years published on this layer). No license or terms stated. The source rows are CRIS
person rows with one person kept per crash ("No duplicating crash ids"): Crash_ID repeats only
twice (one byte-identical pair, one pair with conflicting dates/severity), so `reduce` keeps the
more severe of the two. Person columns (age, gender, ethnicity, alcohol result, person type) are
never read.

Time: Crash_Date is a DateOnly field ("2025-01-03"), Crash_Time an HHMM integer (always valid,
agrees with Hour_of_Day); both are local Central time. Date filters work on DateOnly
(`Crash_Date >= TIMESTAMP '...'` returns the expected rows).

Counts: injured = Crash_Total_Injury_Count (crash level). There is no crash-level death count
(Person_Death_Count belongs to the one kept person), so killed = 0 when Fatal_Crash_Flag is 0 and
stays empty for fatal crashes. severity = Crash_Severity as published ("K - FATAL INJURY" ...
"99 - UNKNOWN"). Vehicle_Hit_and_Run_Flag describes the kept unit only, so only "Yes" is stored
(True); "No" is left empty. 3,562 rows have no coordinates.
"""
import re
from datetime import date, datetime

from ..base import SourceSpec, number, point, sane, text

_CODE = re.compile(r"^\d+\s*-\s*")
_UNKNOWN = {"UNKNOWN", "NO DATA", "NOT REPORTED", "N/A", "OTHER (EXPLAIN IN NARRATIVE)"}


def _label(value) -> str | None:
    value = text(value)
    value = _CODE.sub("", value) if value else None
    return None if not value or value.upper() in _UNKNOWN else value


def _day(value) -> date | None:
    value = text(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def _when(raw: dict) -> datetime | None:
    day = _day(raw.get("Crash_Date"))
    if day is None:
        return None
    clock = number(raw.get("Crash_Time"))
    hour, minute = divmod(clock, 100) if clock is not None else (0, 0)
    if hour > 23 or minute > 59:
        hour = minute = 0
    return datetime(day.year, day.month, day.day, hour, minute)


def _road(raw: dict) -> str | None:
    street = _label(raw.get("Street_Name"))
    house = _label(raw.get("Street_Number"))
    return f"{house} {street}" if street and house else street


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("Latitude"), raw.get("Longitude"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    flag = number(raw.get("Fatal_Crash_Flag"))
    return {
        "source_id": text(raw.get("Crash_ID")),
        "crash_datetime": sane(_when(raw), earliest=2025),
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": number(raw.get("Crash_Total_Injury_Count")),
        "killed": 0 if flag == 0 else None,
        "severity": text(raw.get("Crash_Severity")),
        "primary_cause": None,
        "weather": _label(raw.get("Weather_Condition")),
        "lighting": None,
        "crash_type": None,
        "hit_and_run": True if text(raw.get("Vehicle_Hit_and_Run_Flag")) == "Yes" else None,
    }


def reduce(rows: list[dict]) -> dict:
    """Two rows with one Crash_ID: keep the more severe (fatal, then most injured)."""
    return max(rows, key=lambda r: (r["killed"] is None, r["injured"] or 0))


SPEC = SourceSpec(
    source="dallas_county",
    label="Dallas County, TX crash reports (2025 only)",
    platform="arcgis",
    url="https://services3.arcgis.com/zqe2kwz79KUqUvxC/arcgis/rest/services/2025_traffic_accidents_no_duplicates/FeatureServer/0",
    date_field="Crash_Date",
    parse=parse,
    states=[48],
    bbox=(-97.1, 32.5, -96.45, 33.05),
    tz="America/Chicago",
    page_size=1000,
    reduce=reduce,
    notes="TxDOT CRIS crashes in Dallas County for 2025 only (static). Deaths not counted: killed is 0 for "
          "non-fatal crashes and empty for fatal ones.",
    refresh_days=30,
)
