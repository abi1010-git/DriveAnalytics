"""Johns Creek, GA Police "Accident" reports (Socrata gezc-jm4k on policeview.johnscreekga.gov).

Checked Nov 2026: 31,349 rows, one per crash report, 2010-02-16 to 2026-11-14, updated
daily. No license or terms of use are stated in the dataset metadata (license and
attribution fields are empty); check with the city before redistributing.

Ids: accidentid (equal to case_id on all but 6 rows). 16 ids appear twice: mostly an
original plus a supplemental report (supprept = "True") of the same crash, a few look like
different crashes sharing a number. reduce() keeps the original (non-supplement) row, so
those few distinct crashes collapse to one.

Time: `occured` is a floating timestamp, but on ~45% of rows its clock part is when the
report was entered (with seconds) or midnight, while `timeoccurred` ("HHMM") is the crash
time. crash_datetime = date of `occured` + `timeoccurred`. On ~6% of rows the clock in
`occured` is earlier than `timeoccurred`, so for late-night crashes entered after midnight
the date may be a day late; the source gives nothing better.

Coordinates: geox is latitude and geoy is longitude (checked: geox 33.81..34.10,
geoy -84.47..-84.08); ~8% of rows have none. No severity, injury counts or hit-and-run
field: injtakento (hospital, ~1.2k rows) only says someone was transported, so severity,
injured and killed stay empty. rdconditiondesc holds the manner of collision.
"""
from datetime import datetime

from ..base import SourceSpec, floating, point, sane, text


def crash_time(raw: dict) -> datetime | None:
    occured = floating(raw.get("occured"))
    if occured is None:
        return None
    hhmm = (raw.get("timeoccurred") or "").strip()
    if len(hhmm) == 4 and hhmm.isdigit() and int(hhmm[:2]) < 24 and int(hhmm[2:]) < 60:
        return occured.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]), second=0, microsecond=0)
    return occured


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("geox"), raw.get("geoy"))
    street, cross = text(raw.get("street")), text(raw.get("intersection"))
    return {
        "source_id": text(raw.get("accidentid")),
        "crash_datetime": sane(crash_time(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": f"{street} & {cross}" if street and cross else street or cross,
        "injured": None,
        "killed": None,
        "severity": None,
        "primary_cause": None,
        "weather": text(raw.get("weatherdesc")),
        "lighting": text(raw.get("lightconddesc")),
        "crash_type": text(raw.get("rdconditiondesc")),
        "hit_and_run": None,
        "_supplement": raw.get("supprept") == "True",  # only used by reduce(); not a LocalCrash column
    }


def reduce(rows: list[dict]) -> dict:
    """Several reports with one accidentid: keep the first original, not a supplement."""
    return next((r for r in rows if not r.get("_supplement")), rows[0])


SPEC = SourceSpec(
    source="johns_creek",
    label="Johns Creek, GA police crash reports",
    platform="socrata",
    url="https://policeview.johnscreekga.gov/resource/gezc-jm4k.json",
    date_field="occured",
    parse=parse,
    states=[13],
    bbox=(-84.55, 33.75, -84.0, 34.15),
    tz="America/New_York",
    page_size=50000,
    reduce=reduce,
    notes="No severity or injury counts; no license stated by the publisher.",
)
