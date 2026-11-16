"""KDOT statewide crash layer "Transportation/Accidents" (ArcGIS FeatureServer on kanplan.ksdot.gov).

Checked Nov 2026: 607,894 rows from 2016-01-01; this source loads 2019 onward only (419,923
rows: 2,712 FATAL, 96,907 INJURY, 320,304 PROPERTY DAMAGE ONLY), newest crash 2026-11-09.
One row per crash keyed by ACCIDENT_KEY (e.g. "20260434933"), but 27 keys come back 4-16
times: the service returns the same OBJECTID repeatedly (a join artefact), and the copies are
identical, so the loader's per-id collapse keeps one. Every row has LATITUDE/LONGITUDE.
The server's maxRecordCount is 25,000, but a 25,000-row page with all fields fails with
error 500, so pages are 10,000. ACC_YEAR filters worked when checked, but the loader
filters on dates only.
Reporting lag is long: in Nov 2026 the layer held ~4,500-5,000 crashes for months of 2025 but
3,598 for March 2026, ~2,000 a month for June-September 2026 and 1,498 for October, so recent
months fill in over many months; updates re-read 180 days. No license or terms are stated on the service.

Time: DATE_OF_ACCIDENT is a date only, stored as local midnight (the service declares
dateFieldsTimeReference America/Chicago and returns e.g. 2026-11-09 06:00 UTC = 00:00 CST,
2026-10-06 05:00 UTC = 00:00 CDT), so epoch_is_local stays False. The time of day is only
published as ACC_HOUR ("16"); crash_datetime is the date at that hour (minutes unknown, so
:00), or midnight when ACC_HOUR is empty (1,159 rows since 2019).

Fields: injured = DISABLING_INJURIES + NON_INCAPACITATING_INJURIES + POSSIBLE_INJURIES,
killed = FATALITIES, severity = ACC_SEVERITY. There is no road-name field (ON_ROAD_TYPE is
only a class such as "Local Route"), so road stays empty; no hit-and-run field either.
crash_type is CWOV_FHE_ACC_TYPE (manner of a vehicle-vehicle collision, e.g. "REAR END")
or else ACCIDENT_CLASS_FHE_DESC ("COLL W ANIMAL"). primary_cause is DRIVER_CIRCUMSTANCE
when given. Driver ages and report image links are published but not stored.
"""
from datetime import timedelta

from ..base import SourceSpec, epoch, number, point, sane, text

INJURY_COUNTS = ("DISABLING_INJURIES", "NON_INCAPACITATING_INJURIES", "POSSIBLE_INJURIES")


def _when(raw: dict):
    day = epoch(SPEC, raw.get("DATE_OF_ACCIDENT"))
    if day is None:
        return None
    hour = number(raw.get("ACC_HOUR"))
    if hour is not None and hour < 24:
        day = day.replace(hour=0, minute=0, second=0) + timedelta(hours=hour)
    return day


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in INJURY_COUNTS]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    return {
        "source_id": text(raw.get("ACCIDENT_KEY")),
        "crash_datetime": sane(_when(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": None,
        "injured": _injured(raw),
        "killed": number(raw.get("FATALITIES")),
        "severity": text(raw.get("ACC_SEVERITY")),
        "primary_cause": text(raw.get("DRIVER_CIRCUMSTANCE")),
        "weather": text(raw.get("WEATHER_CONDITIONS_DESC")),
        "lighting": text(raw.get("LIGHT_CONDITIONS_DESC")),
        "crash_type": text(raw.get("CWOV_FHE_ACC_TYPE")) or text(raw.get("ACCIDENT_CLASS_FHE_DESC")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="kansas",
    label="Kansas DOT crash reports (statewide, from 2019)",
    platform="arcgis",
    url="https://kanplan.ksdot.gov/arcgis_web_adaptor/rest/services/Transportation/Accidents/FeatureServer/0",
    date_field="DATE_OF_ACCIDENT",
    where="DATE_OF_ACCIDENT >= TIMESTAMP '2019-01-01 00:00:00'",
    parse=parse,
    states=[20],
    bbox=(-102.1, 36.95, -94.55, 40.05),
    tz="America/Chicago",
    page_size=10000,
    overlap=timedelta(days=180),
    notes="Statewide, bounded to 2019 onward (the service goes back to 2016). Reports arrive months late, so "
          "recent months are far from complete. Time of day is the hour only; "
          "no road names or hit-and-run flag.",
)
