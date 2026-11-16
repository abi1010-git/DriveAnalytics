"""Delaware statewide "Public Crash Data" (Socrata 827n-m6xc, DSHS; mirror of the FirstMap
ArcGIS layer DE_Public_Crash_Data).

Checked Nov 2026: 591,222 rows, one per crash, 2009-01-01 to 2026-04-30 local time; published
monthly around the 5th and covering "2009 through six months ago", so a run mainly adds
complete 2025 statewide data. `where` limits the load to crashes from 2019-01-01 local
(266,756 rows) to bound the first load. No license is stated in the metadata (license field
empty); attribution: Delaware Department of Safety and Homeland Security. The description says
the data is not an official record of any crash.

Time: crash_datetime is a FIXED timestamp in UTC ("...Z"), not floating: rows at
2020-01-01T00:37Z carry year 2019 and day "Tuesday" (Dec 31, 2019 in Delaware), and date-only
crashes sit at 04:00/05:00Z (local midnight). It is converted to America/New_York wall time.
The loader's incremental filter literal is read by Socrata as UTC, a 4-5 h shift that the
3-day overlap absorbs.

Ids: there is no report or case number. The Socrata columns hold no id at all and the ArcGIS
layer only has OBJECTID, which is reassigned when the layer is republished. source_id is
"<crash_datetime UTC>|<latitude>|<longitude>" with coordinates at 5 decimals as published.
Risk: 88 rows since 2019 (0.03%) share a key with another crash and collapse into one; if
DSHS later moves a crash's point or time, the edited crash gets a new id and the old row stays
as a duplicate. Rows with no coordinates keep an empty coordinate part in the id.

Severity is crash_class_desc ("Fatality Crash", "Personal Injury Crash", "Property Damage
Only", "Non-Reportable"); "NA" placeholders become None. No road name, injury counts or
hit-and-run flag are published.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..base import SourceSpec, point, sane, text


def clean(value) -> str | None:
    value = text(value)
    return None if value == "NA" else value


def utc_to_local(value) -> datetime | None:
    """Socrata fixed timestamp ("2023-11-01T17:30:00.000Z") -> naive Delaware wall time."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(SPEC.tz)).replace(tzinfo=None)


def _coord(value) -> str:
    try:
        return f"{float(value):.5f}"
    except (TypeError, ValueError):
        return ""


def crash_id(raw: dict) -> str | None:
    when = text(raw.get("crash_datetime"))
    if not when:
        return None
    return f"{when[:19]}|{_coord(raw.get('latitude'))}|{_coord(raw.get('longitude'))}"


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("latitude"), raw.get("longitude"))
    return {
        "source_id": crash_id(raw),
        "crash_datetime": sane(utc_to_local(raw.get("crash_datetime"))),
        "latitude": lat,
        "longitude": lon,
        "road": None,
        "injured": None,
        "killed": None,
        "severity": clean(raw.get("crash_class_desc")),
        "primary_cause": clean(raw.get("pri_contrib_circum_desc")),
        "weather": clean(raw.get("weather_1_desc")),
        "lighting": clean(raw.get("light_cond_desc")),
        "crash_type": clean(raw.get("impact_desc")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="delaware",
    label="Delaware statewide crash reports",
    platform="socrata",
    url="https://data.delaware.gov/resource/827n-m6xc.json",
    date_field="crash_datetime",
    parse=parse,
    states=[10],
    bbox=(-75.85, 38.4, -74.95, 39.9),
    tz="America/New_York",
    where="crash_datetime >= '2019-01-01T05:00:00'",  # 2019-01-01 00:00 local; the field is UTC
    page_size=50000,
    notes="Statewide, about six months behind; no crash id (built from time and point); from 2019 on.",
)
