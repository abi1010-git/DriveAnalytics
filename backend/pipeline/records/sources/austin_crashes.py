"""Austin, TX "Austin Crash Report Data - Crash Level Records" (TxDOT CRIS via Vision Zero,
Socrata y2wy-tgr5 on datahub.austintexas.gov).

Checked Nov 2026: 235,371 rows, one per crash, 2010-01-01 to 2026-10-30 (CRIS reports lag a
couple of weeks), public domain. These are filed police reports, separate from the "austin"
live incident feed. source_id is cris_crash_id (unique; 3 manually created is_temp_record rows
have none and are skipped, as would any is_deleted row).

Time: crash_timestamp is true UTC (e.g. 05:00 for a 00:00 Central crash); the dataset also
publishes crash_timestamp_ct, the same moment in US/Central wall time, which is used as-is for
crash_datetime and as the date_field. Severity is crash_sev_id mapped to the dataset's own
labels (0=UNKNOWN, 1=INCAPACITATING INJURY, 2=NON-INCAPACITATING INJURY, 3=POSSIBLE INJURY,
4=KILLED, 5=NOT INJURED). injured = tot_injry_cnt (= serious + non-incapacitating + possible,
deaths not included), killed = death_cnt. No cause, weather, lighting or hit-and-run fields.
"""
from ..base import SourceSpec, floating, number, point, sane, text

SEVERITY = {0: "UNKNOWN", 1: "INCAPACITATING INJURY", 2: "NON-INCAPACITATING INJURY", 3: "POSSIBLE INJURY",
            4: "KILLED", 5: "NOT INJURED"}


def _true(value) -> bool:
    return value is True or str(value).lower() == "true"


def parse(raw: dict) -> dict | None:
    if _true(raw.get("is_deleted")) or _true(raw.get("is_temp_record")):
        return None
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    sev = number(raw.get("crash_sev_id"))
    return {
        "source_id": text(raw.get("cris_crash_id")),
        "crash_datetime": sane(floating(raw.get("crash_timestamp_ct"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("address_display")),
        "injured": number(raw.get("tot_injry_cnt")),
        "killed": number(raw.get("death_cnt")),
        "severity": SEVERITY.get(sev) if sev is not None else None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("collsn_desc")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="austin_crashes",
    label="Austin, TX crash reports (TxDOT CRIS)",
    platform="socrata",
    url="https://datahub.austintexas.gov/resource/y2wy-tgr5.json",
    date_field="crash_timestamp_ct",
    parse=parse,
    states=[48],
    bbox=(-98.1, 29.95, -97.4, 30.65),
    tz="America/Chicago",
    page_size=50000,
    notes="Filed CRIS crash reports (lag ~2 weeks); distinct from the live 'austin' incident feed.",
)
