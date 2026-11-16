"""Baton Rouge, LA "Baton Rouge Traffic Crash Incidents" (Socrata 7wah-qncc on data.brla.gov).

Checked Nov 2026: 64,798 rows, 2021-01-27 to 2026-11-14, public domain. Rows are per crash
(63,736 distinct incident_number; the extra rows are almost all exact repeats, the loader keeps
the last one; 15 rows without an incident_number are skipped). Every row has coordinates.

crash_date is a floating timestamp but carries no real time of day: all 64,798 rows read
01:00:00, so the crash time is not published. We keep the date and store it at 00:00 rather
than present 01:00 as a crash time.

There are no injury or death counts, only 0/1 flags. Severity is composed from them:
has_fatality=1 -> "Fatal", else has_injury=1 -> "Injury", else both 0 -> "No injury"
(fatal rows have has_injury=0 in this data, so the fatality flag is checked first).
injured/killed stay empty.
"""
from ..base import SourceSpec, floating, number, point, sane, text


def _flag(value) -> bool | None:
    value = number(value)
    return None if value is None else value > 0


def _severity(raw: dict) -> str | None:
    fatal, injury = _flag(raw.get("has_fatality")), _flag(raw.get("has_injury"))
    if fatal:
        return "Fatal"
    if injury:
        return "Injury"
    if fatal is False and injury is False:
        return "No injury"
    return None


def _day(value):
    when = floating(value)
    return when.replace(hour=0, minute=0, second=0, microsecond=0) if when else None


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    return {
        "source_id": text(raw.get("incident_number")),
        "crash_datetime": sane(_day(raw.get("crash_date"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("street_name")),
        "injured": None,
        "killed": None,
        "severity": _severity(raw),
        "primary_cause": text(raw.get("primary_factor")),
        "weather": text(raw.get("weather")),
        "lighting": text(raw.get("lighting")),
        "crash_type": text(raw.get("manner_of_collision")),
        "hit_and_run": _flag(raw.get("is_hit_and_run")),
    }


SPEC = SourceSpec(
    source="baton_rouge",
    label="Baton Rouge, LA crash reports",
    platform="socrata",
    url="https://data.brla.gov/resource/7wah-qncc.json",
    date_field="crash_date",
    parse=parse,
    states=[22],
    bbox=(-91.4, 30.2, -90.85, 30.75),
    tz="America/Chicago",
    page_size=50000,
    notes="Date only (no crash time); severity from fatality/injury flags; no injury counts.",
)
