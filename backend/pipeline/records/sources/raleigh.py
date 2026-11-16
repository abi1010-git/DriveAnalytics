"""Raleigh, NC Police Department "Reported Crash Locations" (ArcGIS item 3f503c43a0bd4490be7dec17650bcda9).

Checked Nov 2026: 272,310 rows, one per crash (key_crash unique; LocalUse, the RPD report
number, repeats 130 times so it is not used as the id). Dates run 2011-05-30 to 2026-11-13,
but 2011-2014 hold only 16 stray rows; the publisher describes the period as "2015-Present",
updated daily. Built from the NC DMV-349 crash form.

Time convention (mixed, checked against Crash_Date_Hour): rows loaded before mid-2024 store
DateOfCrash as true UTC; newer rows (from about mid-2024, the ones whose LocationCity is
blank-padded) store local wall time as if it were UTC. parse() picks per row whichever reading
matches Crash_Date_Hour and falls back to UTC. Incremental `DateOfCrash >= TIMESTAMP` filters
work (the <=5 h skew is covered by the 3-day overlap).

Counts: killed and type_a/b/c_injury per crash (injured = A+B+C, null on ~17% of older rows).
No severity label is published, so severity stays empty. Coordinates: the feature geometry
lands inside the city box more often than LocationLatitude/LocationLongitude (270k vs 267k),
so geometry is used first. No lighting or hit-and-run fields.

Terms (item licenseInfo): no warranty; data "may be amended or corrected ... at any time", and
"Misuse of the data may subject a party to criminal prosecution for false advertising under
NC GS § 14-117."
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..base import SourceSpec, number, point, sane, text


def _when(raw: dict) -> datetime | None:
    try:
        moment = datetime.fromtimestamp(int(raw.get("DateOfCrash")) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    as_utc = moment.astimezone(ZoneInfo(SPEC.tz)).replace(tzinfo=None)
    as_local = moment.replace(tzinfo=None)
    hour = raw.get("Crash_Date_Hour")
    if hour == as_local.hour and hour != as_utc.hour:
        return as_local
    return as_utc


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in ("type_a_injury", "type_b_injury", "type_c_injury")]
    counts = [c for c in counts if c is not None]
    return sum(counts) if counts else None


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("LocationLatitude"), raw.get("LocationLongitude"))
    return {
        "source_id": text(raw.get("key_crash")),
        "crash_datetime": sane(_when(raw), earliest=2011),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("LocationRoadNameOn")),
        "injured": _injured(raw),
        "killed": number(raw.get("killed")),
        "severity": None,
        "primary_cause": None,
        "weather": text(raw.get("WeatherCondition1")),
        "lighting": None,
        "crash_type": text(raw.get("FirstHarmfulEvent")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="raleigh",
    label="Raleigh, NC police crash reports",
    platform="arcgis",
    url="https://utility.arcgis.com/usrsvcs/servers/3f503c43a0bd4490be7dec17650bcda9/rest/services/Crash_Reports/FeatureServer/0",
    date_field="DateOfCrash",
    parse=parse,
    states=[37],
    bbox=(-78.95, 35.6, -78.3, 36.1),
    tz="America/New_York",
    page_size=2000,
    notes="Raleigh PD reports, essentially 2015 onward. No severity label; injured = type A+B+C. "
          "Misuse may be prosecuted under NC GS 14-117.",
)
