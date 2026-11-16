"""Gainesville, FL Police Department "Traffic Crashes" (Socrata iecn-3sxx).

Checked Nov 2026: 81,553 rows, one per crash, 2011-01-01 to 2026-09-10, city streets under GPD
jurisdiction only. License: Public Domain (attribution "Gainesville Police Department (GPD)").
Florida Statutes 316.066 keep crash reports confidential for 60 days, so the newest rows are
always at least ~60 days old.

Id: case_number is NOT unique (18 repeats, e.g. "0", and repeats that are different crashes on
different dates); dhsmv_number (the state DHSMV crash report number) is present and unique on
every row, so it is the source_id.

accident_date is a floating local timestamp. Coordinates: latitude/longitude are used; the
`location` point disagrees with them on ~27% of rows (it looks offset from another record), so
it is ignored. 4,849 rows have no latitude/longitude. Only fatality counts are published
(totalfatalities); no injury counts or severity label, so those stay empty.
"""
from ..base import SourceSpec, floating, number, point, sane, text


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    return {
        "source_id": text(raw.get("dhsmv_number")),
        "crash_datetime": sane(floating(raw.get("accident_date")), earliest=2011),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("occurred_on")),
        "injured": None,
        "killed": number(raw.get("totalfatalities")),
        "severity": None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": None,
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="gainesville",
    label="Gainesville, FL police crash reports (60+ days delayed)",
    platform="socrata",
    url="https://data.cityofgainesville.org/resource/iecn-3sxx.json",
    date_field="accident_date",
    parse=parse,
    states=[12],
    bbox=(-82.5, 29.5, -82.15, 29.8),
    tz="America/New_York",
    page_size=50000,
    notes="Published at least 60 days after the crash (FL 316.066). Deaths only; no injury counts.",
)
