"""Cincinnati, OH "Cincinnati Police Department Reported Traffic Crashes" (Socrata 7iz8-ecuw).

Checked Nov 2026: 457,386 rows but only 225,109 reports: ONE ROW PER PERSON (driver, occupant
or pedestrian; unitno/typeofperson/injuries vary, crash fields are identical within a report).
Crash dates 2012-01 to 2026-11-11, public domain. `reduce` folds the rows into one crash.

Dates: eventdate is the crash time, reportdate when the report was taken (equal or later in
all but 19 reports). crash_datetime uses eventdate (floating local time); 2 rows without it
and a few placeholder years (1900) are skipped. reportdate is the date_field so incremental
runs also catch reports filed some days after the crash.

Injuries: the `injuries` value is per person and uses two Ohio OH-1 code lists (pre-2019
"1 - No Injury / None Reported" .. "5 - Fatal", later "1 - Fatal" .. "5 - No Apparent Injury",
plus the misspelling "No Apparenty Injury"), so it is matched on the label, not the number.
killed = persons labelled Fatal; injured = persons with any other injury label (fatalities not
included, like Chicago and TxDOT counts); unknown/blank labels count as neither, and a crash
where no person has a known label gets None. Occupants are listed far less often than drivers,
so these are counts of the people the report lists. A handful of reports disagree with
crashseverity (e.g. a Fatal person on a "Serious Injury Suspected" crash); both are kept as
published. severity is crashseverity.
"""
import re

from ..base import SourceSpec, floating, point, sane, text

_CODE = re.compile(r"^\s*\d+\s*-\s*")
_NOT_INJURED = {"no injury / none reported", "no apparent injury", "no apparenty injury"}
_INJURED = {"possible", "non-incapacitating", "incapacitating", "suspected serious injury",
            "suspected minor injury", "possible injury"}


def person_outcome(value) -> tuple[int | None, int | None]:
    """(injured, killed) for one person's `injuries` label."""
    label = _CODE.sub("", text(value) or "").lower()
    if label == "fatal":
        return 0, 1
    if label in _INJURED:
        return 1, 0
    if label in _NOT_INJURED:
        return 0, 0
    return None, None


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    injured, killed = person_outcome(raw.get("injuries"))
    return {
        "source_id": text(raw.get("reportnumber")),
        "crash_datetime": sane(floating(raw.get("eventdate"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("address")),
        "injured": injured,
        "killed": killed,
        "severity": text(raw.get("crashseverity")),
        "primary_cause": None,
        "weather": text(raw.get("weather")),
        "lighting": text(raw.get("lightconditionsprimary")),
        "crash_type": text(raw.get("mannerofcrash")),
        "hit_and_run": None,
    }


def _total(values) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def reduce(rows: list[dict]) -> dict:
    """One crash from its person rows: crash fields from the first row, counts summed."""
    return {**rows[0], "injured": _total(r["injured"] for r in rows), "killed": _total(r["killed"] for r in rows)}


SPEC = SourceSpec(
    source="cincinnati",
    label="Cincinnati, OH crash reports",
    platform="socrata",
    url="https://data.cincinnati-oh.gov/resource/7iz8-ecuw.json",
    date_field="reportdate",
    parse=parse,
    states=[39],
    bbox=(-84.85, 38.95, -84.25, 39.35),
    tz="America/New_York",
    page_size=50000,
    reduce=reduce,
    notes="Per-person rows reduced to one crash; injured/killed counted from the persons listed.",
)
