"""Illinois DOT statewide crashes, 2021-2025 (ArcGIS Online, one service per year).

Checked Nov 2026. Layer 0 of each service is one row per crash (person/vehicle extracts are
separate layers and not read). Row counts: 2025 CrashExtract2025 303,087; 2024 CRASHES__2024
303,927; 2023 CRASHES_2023 300,144 (1,000 CrashIDs appear twice as identical rows apart from
OBJECTID; the loader's per-id collapse keeps one); 2022 CRASHES_2022 298,431; 2021
CRASHES2021 295,634. Service names are not consistent (CRASHES___2025 is the same 2025 data
in the old layout; CrashExtract2025 is used because it has street names). IDOT publishes a
year only after it closes, so there is no 2026 data yet: add the 2026 service to `urls` when
it appears. CrashID is unique within each year and, in a sample of 400 ids per adjacent pair
of years whose id ranges overlap, never repeated across years, so it is the source id as is.
No licence or terms are stated on the services (copyrightText empty).

Time: the field types differ by year. CrashDate is a DateOnly "2025-12-31" in 2025 and an
epoch date in 2021-2024 (local midnight in 2024, UTC midnight in 2023), and TimeOfCrash is
"165800" in 2025 but "04:00 PM" earlier. The crash time is therefore built from CrashYr
(two digits), CrashMonth and CrashDay plus TimeOfCrash, which matched CrashHour in all
15,000 rows sampled; CrashHour is the fallback (ten 2025 rows hold "0000000000"). The loader's
`CrashDate >= TIMESTAMP '...'` filter works on every year (on 2025's DateOnly field it
compares whole days), so incremental updates work, though they will only find new rows once
a new year's service is added.

Coordinates: TSCrashLatitude/TSCrashLongitude (text in 2025, numbers before) are used, with
the WGS84 geometry as fallback. They are more complete than the geometry: in 2025, 302,556
rows have them while the geometry is valid for 302,543; rows without a location carry a
projected (0, 0) point that lands in Oklahoma and is dropped by the bbox.

Fields: severity is CrashSeverity ("Fatal", "Injury", "Property Damage"); injured is
AInjuries + BInjuries + CInjuries (equal to TotalInjured in every 2025 and 2023 row); killed
is TotalFatals. road is HighwayorStreetName, published only from 2025 (earlier years have
only route numbers, so road stays empty). HitAndRun is 0/1 in 2025 and "N"/"Y" before.
"""
import re
from datetime import datetime

from ..base import SourceSpec, number, point, sane, text

BASE = "https://services2.arcgis.com/aIrBD8yn1TDTEXoz/arcgis/rest/services"
URLS = [f"{BASE}/{name}/FeatureServer/0" for name in
        ("CRASHES2021", "CRASHES_2022", "CRASHES_2023", "CRASHES__2024", "CrashExtract2025")]
NOT_STATED = {"(N/A)", "(UNK)", "None"}
_HHMMSS = re.compile(r"^(\d\d)(\d\d)(\d\d)$")
_CLOCK = re.compile(r"^(\d{1,2}):(\d\d)\s*([AP]M)$", re.I)


def _text(value) -> str | None:
    value = text(value)
    return None if value in NOT_STATED else value


def _time(raw: dict) -> tuple[int, int] | None:
    value = text(raw.get("TimeOfCrash")) or ""
    if m := _HHMMSS.match(value):
        hour, minute = int(m[1]), int(m[2])
    elif m := _CLOCK.match(value):
        hour, minute = int(m[1]) % 12 + (12 if m[3].upper() == "PM" else 0), int(m[2])
    else:
        hour, minute = number(raw.get("CrashHour")), 0
    return (hour, minute) if hour is not None and hour < 24 and minute < 60 else None


def _when(raw: dict) -> datetime | None:
    year, month, day = (number(raw.get(k)) for k in ("CrashYr", "CrashMonth", "CrashDay"))
    clock = _time(raw)
    if year is None or month is None or day is None or clock is None:
        return None
    try:
        return datetime(year + 2000 if year < 100 else year, month, day, *clock)
    except ValueError:
        return None


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in ("AInjuries", "BInjuries", "CInjuries")]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def _point(raw: dict) -> tuple[float | None, float | None]:
    lat, lon = point(SPEC, raw.get("TSCrashLatitude"), raw.get("TSCrashLongitude"))
    return (lat, lon) if lat is not None else point(SPEC, raw.get("_lat"), raw.get("_lon"))


def parse(raw: dict) -> dict | None:
    crash_id = number(raw.get("CrashID"))
    lat, lon = _point(raw)
    return {
        "source_id": str(crash_id) if crash_id else None,
        "crash_datetime": sane(_when(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": _text(raw.get("HighwayorStreetName")),
        "injured": _injured(raw),
        "killed": number(raw.get("TotalFatals")),
        "severity": _text(raw.get("CrashSeverity")),
        "primary_cause": _text(raw.get("Cause1")),
        "weather": _text(raw.get("WeatherCond")),
        "lighting": _text(raw.get("LightingCond")),
        "crash_type": _text(raw.get("TypeOfFirstCrash")),
        "hit_and_run": {"1": True, "Y": True, "0": False, "N": False}.get(str(raw.get("HitAndRun")).strip()),
    }


SPEC = SourceSpec(
    source="illinois",
    label="Illinois DOT crash reports",
    platform="arcgis",
    url=URLS[-1],
    urls=URLS,
    date_field="CrashDate",
    parse=parse,
    states=[17],
    bbox=(-91.7, 36.8, -86.9, 42.7),
    tz="America/Chicago",
    page_size=2000,
    notes="Statewide 2021-2025 (about 1.5M crashes), published yearly after the year closes; "
          "add each new CrashExtract<year> service to urls. Street names only from 2025.",
    refresh_days=30,
)
