"""COMPASS (Community Planning Association of Southwest Idaho) "All Crash Locations" (ArcGIS
FeatureServer COMPASSData/CrashData, layer 0): Ada and Canyon counties only, Idaho.

Checked Nov 2026: 174,038 rows for 2008-2025 (no 2026 yet); this source loads 2019 onward:
76,306 rows with a date (Ada 47,989, Canyon 28,359; 2019: 11,050 ... 2025: 11,512, 2020 lower
at 8,758). 42 rows of 2024 have no date at all and are left out by the server-side filter.
One row per crash: serialnumber (e.g. "25C718763") is unique except for one pair of identical
rows, which the loader's per-id collapse merges. Every row has a point. maxRecordCount is
180,000; pages of 20,000 work. The object-id field is lowercase "objectid". Published
yearly, so it is re-read monthly (refresh_days=30). No license is stated (copyright text empty).

Time: accident_date is the date only, stored as UTC midnight (the service declares
dateFieldsTimeReference UTC), so its UTC date is the local date (checked: it matched the date
in accidentdate on every row). The local time is in the text field accidentdate, written in
three formats over the years: "2025-12-31 12:22:00", "11/7/2020 01:54" and
"6/19/2023 3:49:00 PM" (it always agreed with accidenttime). 109 rows have an unknown time
("12/29/2019 -U") and get local midnight; rows with no text fall back to accident_date.

Fields: injured = injuries (identical to numberofinjuries on every row), killed = fatalities,
severity = severity ("Property Dmg Report", "C/B/A Injury Accident", "Fatal Accident").
road = street1, with street2 after " & " when the crash is at an intersection. No cause,
collision type or hit-and-run fields are published. Agency case numbers are not stored.
"""
import re
from datetime import datetime, timezone

from ..base import SourceSpec, number, point, sane, text

FORMATS = ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M")
_DATE_ONLY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _when(raw: dict) -> datetime | None:
    value = text(raw.get("accidentdate"))
    if value:
        for fmt in FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
        match = _DATE_ONLY.match(value)  # "12/29/2019 -U": time unknown
        if match:
            month, day, year = map(int, match.groups())
            try:
                return datetime(year, month, day)
            except ValueError:
                return None
    try:
        moment = datetime.fromtimestamp(int(raw.get("accident_date")) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return datetime(moment.year, moment.month, moment.day)


def _road(raw: dict) -> str | None:
    street, cross = text(raw.get("street1")), text(raw.get("street2"))
    return f"{street} & {cross}" if street and cross else street or cross


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    return {
        "source_id": text(raw.get("serialnumber")),
        "crash_datetime": sane(_when(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": number(raw.get("injuries")),
        "killed": number(raw.get("fatalities")),
        "severity": text(raw.get("severity")),
        "primary_cause": None,
        "weather": text(raw.get("weather")),
        "lighting": text(raw.get("light")),
        "crash_type": None,
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="idaho_compass",
    label="Ada & Canyon counties, ID crash reports (COMPASS)",
    platform="arcgis",
    url="https://swidrdc.org/arcgis/rest/services/COMPASSData/CrashData/FeatureServer/0",
    date_field="accident_date",
    where="accident_date >= TIMESTAMP '2019-01-01 00:00:00'",
    parse=parse,
    states=[16],
    bbox=(-117.1, 43.0, -115.9, 44.0),
    tz="America/Boise",
    page_size=20000,
    order_field="objectid",
    refresh_days=30,
    notes="Ada and Canyon counties only (Boise/Nampa area), from 2019 through the last published year "
          "(2025 when checked). No cause or collision-type fields.",
)
