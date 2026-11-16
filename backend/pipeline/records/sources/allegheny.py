"""Allegheny County (Pittsburgh), PA crash data from PennDOT, published by WPRDC on CKAN
(package "allegheny-county-crash-data", one datastore resource per year).

Checked Nov 2026: resources 2021 e3b145c0-..., 2022 980f784b-..., 2023 96777349-...,
2024 4c016b4c-... (10,228 rows) and 2025 c6bedb17-... (10,528 rows; added 2026-09-11).
License CC0 (cc-zero). Published annually, after PennDOT releases a year. One row per
crash: the crash record number is unique in each resource.

Two schemas: 2021-2024 use CRASH_CRN (text), DEC_LAT/DEC_LONG, STREET_NAME; 2025 uses CRN
(numeric), DEC_LATITUDE/DEC_LONGITUDE and has no street name. parse() reads either. Because
the id column differs, paging uses CKAN's own "_id" row number (present in every resource);
source_id is the CRN.

Time: MONTH PRECISION. PennDOT does not allow the crash date to be published (WPRDC's
access note); only CRASH_YEAR, CRASH_MONTH, DAY_OF_WEEK and HOUR_OF_DAY/TIME_OF_DAY exist.
crash_datetime is therefore the first of the crash month at 00:00 - never use it for day or
time-of-day analysis.

Incremental updates cannot work: there is no date column to filter on (date_field is
CRASH_YEAR, a number, kept only because the spec needs one), so incremental=False and every
run reloads all resources (~52k rows, a few requests); refresh_days=30 since WPRDC publishes
once a year. Add the new resource id to RESOURCES when a year is added.

Counts: injured = INJURY_COUNT (all injured people, deaths excluded; equal to TOT_INJ_COUNT in
every 2024 row; it includes possible and unknown-severity injuries, which the per-level
columns of 2021-2024 do not all cover), killed = FATAL_COUNT. severity is MAX_SEVERITY_LEVEL
mapped to PennDOT's labels; the mapping is consistent with the counts (level 1 rows all have
FATAL_COUNT > 0, level 2 rows carry the serious-injury counts, 3 minor, 4 possible, 8 only
unknown-severity injuries, 0 and 9 no injuries). DRIVER_COUNT_* age bands are not stored.
"""
from datetime import datetime

from ..base import SourceSpec, number, point, sane, text

RESOURCES = {
    2021: "e3b145c0-41ba-4cc9-9054-8f686ac59643",
    2022: "980f784b-978b-40c6-b649-f92f90b14dae",
    2023: "96777349-57df-48fb-a1d7-8384786fe71a",
    2024: "4c016b4c-59f0-45ca-981c-718c784b3462",
    2025: "c6bedb17-2d23-49b1-843a-8f6b41e5e5c3",
}
SEVERITY = {0: "Not injured", 1: "Killed", 2: "Suspected serious injury", 3: "Suspected minor injury",
            4: "Possible injury", 8: "Injury - unknown severity", 9: "Unknown"}


def _first(raw: dict, *keys):
    return next((raw[k] for k in keys if raw.get(k) not in (None, "")), None)


def _month(raw: dict) -> datetime | None:
    year, month = number(raw.get("CRASH_YEAR")), number(raw.get("CRASH_MONTH"))
    if not year or not month or month > 12:
        return None
    return datetime(year, month, 1)


def parse(raw: dict) -> dict | None:
    crn = number(_first(raw, "CRN", "CRASH_CRN"))
    lat, lon = point(SPEC, _first(raw, "DEC_LATITUDE", "DEC_LAT"), _first(raw, "DEC_LONGITUDE", "DEC_LONG"))
    return {
        "source_id": str(crn) if crn else None,
        "crash_datetime": sane(_month(raw), earliest=2021),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("STREET_NAME")),
        "injured": number(raw.get("INJURY_COUNT")),
        "killed": number(raw.get("FATAL_COUNT")),
        "severity": SEVERITY.get(number(raw.get("MAX_SEVERITY_LEVEL"))),
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": None,
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="allegheny",
    label="Allegheny County, PA crash reports (PennDOT via WPRDC)",
    platform="ckan",
    url="https://data.wprdc.org/api/3/action/datastore_search_sql",
    urls=list(RESOURCES.values()),
    id_field="_id",
    date_field="CRASH_YEAR",
    parse=parse,
    states=[42],
    bbox=(-80.37, 40.19, -79.68, 40.68),
    tz="America/New_York",
    page_size=5000,
    incremental=False,
    refresh_days=30,
    notes="Month precision only (PennDOT withholds the crash date): crash_datetime is the 1st of the month. "
          "Published annually; always reloaded in full. CC0.",
)
