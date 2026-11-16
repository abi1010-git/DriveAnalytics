"""Tucson Police Department traffic collisions (TPD Open Data), one ArcGIS Online feature
service per year: TPDOpenData_TrafficCollisions_<year>/FeatureServer/0, 2018-2026.

Checked Nov 2026 against the live services (all nine share the same 31 fields): rows per year
2018 6,122 / 2019 6,497 / 2020 5,189 / 2021 5,888 / 2022 5,281 / 2023 5,908 / 2024 5,792 /
2025 5,276 / 2026 4,385 (50,338 in all). One row per crash: AccidentNumber has no duplicates
within a year and encodes the date (YYMMDD + sequence), so it is unique across years too.
Oldest 2018-01-01, newest 2026-11-13. 13-60 rows a year have no coordinates. No license or
copyright is stated in the service metadata. maxRecordCount is 1000.

Time convention: OccurredDate is an ArcGIS DateOnly field returned as "YYYY-MM-DD" text (not
epoch milliseconds), and OccurredHour is local wall time to the hour ("13:00:00"); its profile
peaks at 15-17 h and is lowest at 3-4 h, i.e. local Tucson time (Arizona has no DST). So
crash_datetime = OccurredDate + OccurredHour, minutes always :00; epoch_is_local does not
apply. A row without an hour falls back to midnight of its date. The server accepts the
loader's TIMESTAMP '...' filter on the DateOnly field (checked: same count as DATE '...').
New years need a new URL in `urls`.

Severity is InjurySeverity (e.g. "Non-Incapacitating Injury"); injured / killed are
TotalInjuries / TotalFatalities (published as text). TotalInjuries is 0 or 1 on almost every
row even for multi-person crashes, so it reads more like an "any injury" count; it is loaded
as published. crash_type is CollisionManner ("Rear End (Front to Back)", "Left Turn"...).
"""
from datetime import datetime

from ..base import SourceSpec, number, point, sane, text

YEARS = range(2018, 2027)
BASE_URL = "https://services3.arcgis.com/9coHY2fvuFjG9HQX/arcgis/rest/services"


def occurred(date_value, hour_value) -> datetime | None:
    """("2026-11-13", "13:00:00") -> 2026-11-13 13:00 local."""
    try:
        day = datetime.strptime(str(date_value)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    try:
        hour = int(str(hour_value).split(":")[0])
    except (TypeError, ValueError):
        return day
    return day.replace(hour=hour) if 0 <= hour <= 23 else day


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("Latitude"), raw.get("Longitude"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("AccidentNumber")),
        "crash_datetime": sane(occurred(raw.get("OccurredDate"), raw.get("OccurredHour")), earliest=2018),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("CollisionIntersection")),
        "injured": number(raw.get("TotalInjuries")),
        "killed": number(raw.get("TotalFatalities")),
        "severity": text(raw.get("InjurySeverity")),
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("CollisionManner")),
        "hit_and_run": {"Yes": True, "No": False}.get(text(raw.get("HitAndRun"))),
    }


SPEC = SourceSpec(
    source="tucson",
    label="Tucson, AZ police collision reports",
    platform="arcgis",
    url=f"{BASE_URL}/TPDOpenData_TrafficCollisions_{YEARS[-1]}/FeatureServer/0",
    urls=[f"{BASE_URL}/TPDOpenData_TrafficCollisions_{year}/FeatureServer/0" for year in YEARS],
    date_field="OccurredDate",
    parse=parse,
    states=[4],
    bbox=(-111.15, 31.98, -110.65, 32.4),
    tz="America/Phoenix",
    page_size=1000,
    notes="City of Tucson (TPD) only, from 2018; time to the hour; one service per year.",
)
