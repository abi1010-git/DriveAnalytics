"""Montgomery County, MD "Crash Reporting - Incidents Data" (Socrata bhju-22kf).

Checked Nov 2026: 127,119 rows, one per crash (report_number unique), 2015-01-01 to
2026-11-11, published weekly, public domain. Severity is only a report type ("Fatal Crash",
"Injury Crash", "Property Damage Crash"); there are no injury or death counts, so those
columns stay empty rather than being guessed. crash_date_time is a floating local timestamp.
"""
from ..base import SourceSpec, floating, point, sane, text


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    return {
        "source_id": text(raw.get("report_number")),
        "crash_datetime": sane(floating(raw.get("crash_date_time"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("road_name")),
        "injured": None,
        "killed": None,
        "severity": text(raw.get("acrs_report_type")),
        "primary_cause": None,
        "weather": text(raw.get("weather")),
        "lighting": text(raw.get("light")),
        "crash_type": text(raw.get("collision_type")),
        "hit_and_run": {"Yes": True, "No": False}.get(raw.get("hit_run")),
    }


SPEC = SourceSpec(
    source="montgomery_md",
    label="Montgomery County, MD crash reports",
    platform="socrata",
    url="https://data.montgomerycountymd.gov/resource/bhju-22kf.json",
    date_field="crash_date_time",
    parse=parse,
    states=[24],
    bbox=(-77.6, 38.9, -76.85, 39.4),
    tz="America/New_York",
    page_size=50000,
    notes="Severity is a report type only; no injury counts.",
)
