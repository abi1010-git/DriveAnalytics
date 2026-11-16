"""Somerville, MA Police "Police Data: Crashes" (Socrata mtik-28va).

Checked Nov 2026: 3,565 rows, one per crash (crashnum unique), 2018-03-23 to 2026-10-14,
refreshed daily with about a one-month delay; excludes crashes under investigation and those
on state roads (Massachusetts State Police). License: Open Data Commons ODbL 1.0, attribution
"Somerville PD". ODbL requires attribution and share-alike: a database derived from this
data that is shared publicly must also be offered under ODbL.

dtcrash is a TEXT column, "YYYY-MM-DD HH:MM:SS" on all but 2 rows, which hold only
"YYYY-MM-DD" (parsed as midnight). Because it is text, the loader's incremental filter
(dtcrash >= 'YYYY-MM-DDTHH:MM:SS') is a string comparison: checked against the live API it
works, except that rows on the `since` day itself sort before the 'T' and are skipped. That
day lies inside the 3-day overlap, so only edits to crashes on that one day can be missed.

Injury columns are counts of people by KABCO level: killed = fatalinjury, injured =
suspected serious + suspected minor + possible injury. Severity is the most severe level
with a count above zero, named as the city's columns name it ("Fatal Injury", ...).
"""
from datetime import datetime

from ..base import SourceSpec, number, point, sane, text

# (column, label from the column's own name), most severe first
LEVELS = [
    ("fatalinjury", "Fatal Injury"),
    ("suspectedseriousinjury", "Suspected Serious Injury"),
    ("suspectedminorinjury", "Suspected Minor Injury"),
    ("possibleinjury", "Possible Injury"),
    ("noapparentinjury", "No Apparent Injury"),
]
FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
           "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p",
           "%Y-%m-%d", "%m/%d/%Y")


def parse_dt(value) -> datetime | None:
    value = text(value)
    for fmt in FORMATS:
        try:
            return datetime.strptime(value, fmt) if value else None
        except ValueError:
            continue
    return None


def severity(raw: dict) -> str | None:
    return next((label for field, label in LEVELS if (number(raw.get(field)) or 0) > 0), None)


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    hurt = [number(raw.get(f)) for f in ("suspectedseriousinjury", "suspectedminorinjury", "possibleinjury")]
    address = text(raw.get("address"))
    if address and address.endswith(" Somerville, MA"):
        address = address[: -len(" Somerville, MA")].strip() or None
    return {
        "source_id": text(raw.get("crashnum")),
        "crash_datetime": sane(parse_dt(raw.get("dtcrash"))),
        "latitude": lat,
        "longitude": lon,
        "road": address,
        "injured": sum(hurt) if None not in hurt else None,
        "killed": number(raw.get("fatalinjury")),
        "severity": severity(raw),
        "primary_cause": None,
        "weather": text(raw.get("weathcond1desc")),
        "lighting": text(raw.get("ambntlightdesc")),
        "crash_type": text(raw.get("manrcolldesc")),
        "hit_and_run": {"Y": True, "N": False}.get(raw.get("hitrunflag")),
    }


SPEC = SourceSpec(
    source="somerville_ma",
    label="Somerville, MA police crash reports",
    platform="socrata",
    url="https://data.somervillema.gov/resource/mtik-28va.json",
    date_field="dtcrash",
    parse=parse,
    states=[25],
    bbox=(-71.17, 42.35, -71.03, 42.43),
    tz="America/New_York",
    page_size=50000,
    notes="About one month delay; no state roads. ODbL: attribution and share-alike required.",
)
