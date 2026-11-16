"""Seattle SDOT "Collisions - All Years", ArcGIS Online SDOT_Collisions_All_Years_1/FeatureServer/0.

These are filed collision reports (SPD and state reports matched by SDOT), distinct from the
live 911 incident feed loaded as "seattle", hence the id "seattle_sdot".

Checked Nov 2026 against the live service: 263,471 rows, one per collision (INCKEY has no
duplicates and is never null; REPORTNO repeats on some rows, so it is not the id). INCDATE
from 2003-10-06 to 2026-11-07; recent months are sparse because reports are added with a lag
(ADDDTTM a few days to weeks after the crash). Geometry only (no lat/lon attributes), so the
loader's merged _lat/_lon are used; some rows have no geometry. Copyright "SDOT"; no license
is stated in the service metadata. maxRecordCount is 2000.

Time convention: INCDATE is a date only, stored as local midnight in true UTC (07:00 UTC in
PDT, 08:00 UTC in PST), so epoch_is_local=False. INCDTTM is local wall-time text, either
"11/7/2026 8:55:00 PM" (202,761 rows) or a bare date "11/3/2026"; parse() prefers it and
falls back to INCDATE (midnight) when it is missing or unreadable.

Counts: INJURIES already includes SERIOUSINJURIES (SERIOUSINJURIES > INJURIES on 0 rows),
so injured = INJURIES alone; killed = FATALITIES. severity = MAXSEVERITYDESC ("Property
Damage Only Collision", "Injury Collision", "Serious Injury Collision", "Fatal Collision";
411 rows null). crash_type = ST_COLLISIONTYPE, else SDOT_COLDESC. There is no hit-and-run
or cause field.
"""
from datetime import datetime, timedelta

from ..base import SourceSpec, epoch, number, point, sane, text


def local_time(value) -> datetime | None:
    """INCDTTM text: "11/7/2026 8:55:00 PM" or "11/3/2026" -> naive local datetime."""
    value = text(value)
    if not value:
        return None
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    when = local_time(raw.get("INCDTTM")) or epoch(SPEC, raw.get("INCDATE"))
    return {
        "source_id": text(raw.get("INCKEY")),
        "crash_datetime": sane(when, earliest=2003),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("LOCATION")),
        "injured": number(raw.get("INJURIES")),
        "killed": number(raw.get("FATALITIES")),
        "severity": text(raw.get("MAXSEVERITYDESC")),
        "primary_cause": None,
        "weather": text(raw.get("WEATHER")),
        "lighting": text(raw.get("LIGHTCOND")),
        "crash_type": text(raw.get("ST_COLLISIONTYPE")) or text(raw.get("SDOT_COLDESC")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="seattle_sdot",
    label="Seattle SDOT collision reports",
    platform="arcgis",
    url="https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/SDOT_Collisions_All_Years_1/FeatureServer/0",
    date_field="INCDATE",
    parse=parse,
    states=[53],
    bbox=(-122.48, 47.47, -122.2, 47.76),
    tz="America/Los_Angeles",
    page_size=2000,
    overlap=timedelta(days=30),  # late-added reports for older dates
    notes="Filed reports from 2003, added with a lag of days to weeks; distinct from the live 'seattle' 911 feed.",
)
