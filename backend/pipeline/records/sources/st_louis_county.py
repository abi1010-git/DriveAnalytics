"""St. Louis County, MO "Vehicle Accidents" (ArcGIS Online Vehicle_Accidents/FeatureServer/0).

Checked Nov 2026 against the live service: 67,988 rows, "Vehicle Accidents in St. Louis
County 2021 - Present", Accident_Date from 2021-01-01 to 2026-11-08 (7,935 rows in 2026).
No license or terms are stated on the service.

Ids: Accident_ID is the crash id, but the layer is the output of a spatial join and repeats
some crashes as identical rows (e.g. one 2024 id appears 8 times, differing only in
OBJECTID/TARGET_FID); the loader's per-id collapse keeps one. 834 rows have Accident_ID 0 and
an empty Report_Number: they cannot be identified stably and are skipped.

Time: Accident_Date is true UTC epoch ms holding local midnight (2021-01-01 06:00 UTC =
00:00 CST; 2026-11-08 06:00 UTC = 00:00 CST), and Accident_Time is the local time as an
integer HHMM (112 = 01:12; never null, never >= 2400; 1,057 rows are 0 and are kept as
00:00 as published). crash_datetime = local date + Accident_Time.

Fields: injured = Number_Injured, killed = Number_Killed (never null). The only severity
information is the Property_Damage_Only 0/1 flag, which is not a label, so severity stays
empty. road is On_Road as published (interstates appear as bare numbers like "70").
11 rows have no latdd and 81 have 0; they are stored without coordinates.
"""
from datetime import timedelta

from ..base import SourceSpec, epoch, number, point, sane, text


def _when(raw: dict):
    day = epoch(SPEC, raw.get("Accident_Date"))
    hhmm = number(raw.get("Accident_Time"))
    if day is None or hhmm is None or hhmm >= 2400 or hhmm % 100 >= 60:
        return None
    return day.replace(hour=0, minute=0, second=0) + timedelta(hours=hhmm // 100, minutes=hhmm % 100)


def parse(raw: dict) -> dict | None:
    accident_id = number(raw.get("Accident_ID"))
    lat, lon = point(SPEC, raw.get("latdd"), raw.get("londd"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(accident_id) if accident_id else None,
        "crash_datetime": sane(_when(raw), earliest=2021),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("On_Road")),
        "injured": number(raw.get("Number_Injured")),
        "killed": number(raw.get("Number_Killed")),
        "severity": None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": None,
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="st_louis_county",
    label="St. Louis County, MO police crash reports",
    platform="arcgis",
    url="https://services2.arcgis.com/w657bnjzrjguNyOy/arcgis/rest/services/Vehicle_Accidents/FeatureServer/0",
    date_field="Accident_Date",
    parse=parse,
    states=[29],
    bbox=(-90.76, 38.37, -90.10, 38.90),
    tz="America/Chicago",
    page_size=2000,
    notes="From 2021. Injury and death counts only; no severity label, cause or conditions. "
          "Rows without a crash id (Accident_ID 0) are skipped.",
)
