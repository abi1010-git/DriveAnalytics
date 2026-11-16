"""ODOT "Initial Fatal Crashes" (ArcGIS MapServer agol/Initial_Fatal_Public, layer 0): fatal
crashes only, preliminary initial reports kept by ODOT's Crash Analysis & Reporting unit.

Checked Nov 2026: 937 rows, of which 83 are flagged REMOVED=1 (withdrawn, e.g. found not to be
a traffic fatality) and excluded server-side; the 854 kept rows run from 2025-01-01 to
2026-11-07 (2025: 459, 2026: 395), so the layer holds only the current and previous year.
ST_ACDT ("CAR Fatal Crash #", year + sequence, e.g. 20261107) is unique among kept rows and is
the id; CASE_NUM is the agency case number and is often incomplete ("26-"). Every row has
LAT/LONGTD and a time. maxRecordCount 2000; the TIMESTAMP filter on ACDT_DT works. No
license or terms text is published on the service.

Time: ACDT_DT is the date only, returned as true UTC of local midnight (07:00 or 08:00 UTC
depending on DST), so epoch_is_local stays False; the time of day is ACDT_TM as an integer
hhmm (1020 = 10:20, matching ACDT_TM_DSPLY "10:20") and is added to the date.

Fields: killed = NUM_FATALS. Injuries are not published (injured stays empty) and there is
no severity label, so severity stays empty rather than restating "fatal". road is ROAD with
ROAD_INT after " & "; crash_type is HARMFUL (most harmful event, e.g. "Head On",
"Pedestrian"); hit_and_run from HIT_RUN Yes/No ("Unknown" -> empty). No weather, lighting or
cause fields. Victim genders, ages, positions and restraint use are published but not stored.
Caveat: a crash removed after it was loaded stays in local_crashes, since updates only read
rows the server still returns.
"""
from datetime import timedelta

from ..base import SourceSpec, epoch, number, point, sane, text


def _when(raw: dict):
    day = epoch(SPEC, raw.get("ACDT_DT"))
    hhmm = number(raw.get("ACDT_TM"))
    if day is None:
        return None
    if hhmm is not None and hhmm // 100 < 24 and hhmm % 100 < 60:
        day = day.replace(hour=0, minute=0, second=0) + timedelta(hours=hhmm // 100, minutes=hhmm % 100)
    return day


def _road(raw: dict) -> str | None:
    road, cross = text(raw.get("ROAD")), text(raw.get("ROAD_INT"))
    return f"{road} & {cross}" if road and cross else road or cross


def parse(raw: dict) -> dict | None:
    if number(raw.get("REMOVED")) == 1:
        return None
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("LAT"), raw.get("LONGTD"))
    crash_no = number(raw.get("ST_ACDT"))
    return {
        "source_id": str(crash_no) if crash_no else None,
        "crash_datetime": sane(_when(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": None,
        "killed": number(raw.get("NUM_FATALS")),
        "severity": None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("HARMFUL")),
        "hit_and_run": {"Yes": True, "No": False}.get(raw.get("HIT_RUN")),
    }


SPEC = SourceSpec(
    source="oregon_fatal",
    label="Oregon fatal crashes (preliminary)",
    platform="arcgis",
    url="https://gis-ext.odot.state.or.us/arcgisserver/rest/services/agol/Initial_Fatal_Public/MapServer/0",
    date_field="ACDT_DT",
    where="REMOVED IS NULL OR REMOVED <> 1",
    parse=parse,
    states=[41],
    bbox=(-124.8, 41.9, -116.4, 46.35),
    tz="America/Los_Angeles",
    page_size=2000,
    overlap=timedelta(days=30),
    notes="Fatal crashes only, from ODOT's preliminary initial reports; covers the current and previous "
          "year. No injury counts, weather or lighting.",
)
