"""HDOT "HiDOTFatalCrashEntry" (Socrata 7cny-nhb8 on highways.hidot.hawaii.gov): fatal crashes
only, as entered by HDOT into its ArcGIS fatal-crash layer.

Checked Nov 2026: 1,506 rows. Rows before 2019 are not crashes with dates: 2003-2011 are
per-county yearly totals dated Dec 31 (fatalsum 5-88), and 2012-2018 rows almost all carry a
year-end placeholder date (e.g. 114 rows on 2012-12-31, 81 on 2018-12-28). So only
crash_date >= 2019-01-01 is loaded: 773 rows (2019: 102 ... 2025: 123, 2026: 77 to
2026-11-03), 806 deaths, every row with a the_geom point.

Id: crashid ("26-028038", the police report number) is missing on 239 of those rows, including
new entries still marked "pending" that get it filled in later, and had no duplicates when
checked. Keying on it would load a pending crash twice (once without, once with the number),
so the id is the ArcGIS globalid instead, which every row has and which stays fixed when the
row is edited. Risk: a crash entered twice as two features would appear twice (none found).

Time: crash_date is a Socrata fixed timestamp holding a date only, at inconsistent instants
(22:00Z through 2023, 08:00Z from 2024, a few 18:00Z/04:00Z). Read in Hawaii time the date
is never after the row's creationdate; read as the UTC date, 94 rows would be created before
their crash. So crash_datetime is the Hawaii calendar date at 00:00 (time of day unknown).

Fields: killed = fatalsum. No injury counts, severity label, weather or lighting are
published. crash_type is vehicle_type (mode of the victim's vehicle, e.g. "Pedestrian",
"MotorCycle"); road is roadname, filled on few rows. The remarks free text (contributing
factors) is not stored. No license is stated on the dataset.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..base import SourceSpec, number, point, sane, text


def _day(value) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(ZoneInfo(SPEC.tz))
    return datetime(local.year, local.month, local.day)


def parse(raw: dict) -> dict | None:
    coords = (raw.get("the_geom") or {}).get("coordinates") or [None, None]
    lat, lon = point(SPEC, coords[1], coords[0]) if len(coords) >= 2 else (None, None)
    return {
        "source_id": text(raw.get("globalid")),
        "crash_datetime": sane(_day(raw.get("crash_date")), earliest=2019),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("roadname")),
        "injured": None,
        "killed": number(raw.get("fatalsum")),
        "severity": None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("vehicle_type")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="hawaii_fatal",
    label="Hawaii fatal crashes",
    platform="socrata",
    url="https://highways.hidot.hawaii.gov/resource/7cny-nhb8.json",
    date_field="crash_date",
    where="crash_date >= '2019-01-01T00:00:00'",
    parse=parse,
    states=[15],
    bbox=(-160.5, 18.8, -154.7, 22.4),
    tz="Pacific/Honolulu",
    page_size=50000,
    overlap=timedelta(days=30),
    notes="Fatal crashes only, from 2019 (earlier rows are yearly totals or placeholder dates). "
          "Date only, no time of day; no injury counts, weather or lighting.",
)
