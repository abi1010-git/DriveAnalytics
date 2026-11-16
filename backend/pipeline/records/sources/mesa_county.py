"""Mesa County, CO crash data "MC_CrashData_Master_2025" (ArcGIS Online FeatureServer, layer 0):
crashes in Mesa County (Grand Junction area) reported by GJPD, Colorado State Patrol,
Fruita, Palisade and De Beque police.

Checked Nov 2026: 19,331 rows from 2018-01-01 to 2025-12-31 (2018: 2,634 ... 2025: 2,229),
one row per crash. The service is a yearly master file (the 2025 name suggests a new service
each year, which would need a new url). Only one row lacks a point. maxRecordCount 2000; the
TIMESTAMP filter works on the DateOnly Crash_Date. No license or terms are stated.
Re-read monthly (refresh_days=30).

Id: CUID (the state crash number) is not unique on its own: 143 values appear twice, each
time for two different crashes in different years (e.g. 2019 and 2022, different places and
times). CUID together with the crash year is unique, so the id is "<year>-<CUID>". One 2025
row has no CUID and is skipped.

Time: Crash_Date is esriFieldTypeDateOnly ("2025-12-31") and Crash_Time is local text in two
formats, "9:46 AM" (older rows) and "3:25:00 PM"; both are parsed here. Two rows with no time
get local midnight.

Fields: injured = Possible_Injury + Suspected_Minor_Injury + Suspected_Serious_Injury (these
matched TotalInjured on 19,261 rows); No_Apparent_Injury counts unhurt people and is left out.
killed = Fatal_Injury, severity = Severity ("No Injury", "Possible Injury", "Minor Injury",
"Major Injury", "Fatality"). crash_type = Crash_Type; road = Location_1 & Location_2.
hit_and_run is true when either of the first two units (TU_1/TU_2_Hit_And_Run) is flagged,
false only when every unit of a one- or two-vehicle crash is flagged 0, else unknown (the flags
are mostly empty before 2025). Driver ages, sexes and the narrative are published but not
stored.
"""
from datetime import date, datetime

from ..base import SourceSpec, number, point, sane, text

INJURY_COUNTS = ("Possible_Injury", "Suspected_Minor_Injury", "Suspected_Serious_Injury")
TIME_FORMATS = ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M")


def _when(raw: dict) -> datetime | None:
    try:
        day = date.fromisoformat(str(raw.get("Crash_Date"))[:10])
    except ValueError:
        return None
    clock = text(raw.get("Crash_Time"))
    for fmt in TIME_FORMATS if clock else ():
        try:
            moment = datetime.strptime(clock, fmt)
        except ValueError:
            continue
        return datetime(day.year, day.month, day.day, moment.hour, moment.minute)
    return datetime(day.year, day.month, day.day)


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in INJURY_COUNTS]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def _hit_and_run(raw: dict) -> bool | None:
    first, second = number(raw.get("TU_1_Hit_And_Run")), number(raw.get("TU_2_Hit_And_Run"))
    if first == 1 or second == 1:
        return True
    vehicles = number(raw.get("TotalVehicles"))
    if first == 0 and vehicles is not None and (vehicles <= 1 or (vehicles == 2 and second == 0)):
        return False
    return None


def _road(raw: dict) -> str | None:
    road, cross = text(raw.get("Location_1")), text(raw.get("Location_2"))
    return f"{road} & {cross}" if road and cross else road or cross


def parse(raw: dict) -> dict | None:
    cuid, when = number(raw.get("CUID")), sane(_when(raw))
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("Latitude"), raw.get("Longitude"))
    return {
        "source_id": f"{when.year}-{cuid}" if cuid and when else None,
        "crash_datetime": when,
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": _injured(raw),
        "killed": number(raw.get("Fatal_Injury")),
        "severity": text(raw.get("Severity")),
        "primary_cause": None,
        "weather": text(raw.get("Weather_Condition_1")),
        "lighting": text(raw.get("Lighting_Conditions")),
        "crash_type": text(raw.get("Crash_Type")),
        "hit_and_run": _hit_and_run(raw),
    }


SPEC = SourceSpec(
    source="mesa_county",
    label="Mesa County, CO crash reports",
    platform="arcgis",
    url="https://services1.arcgis.com/6IRzQDYOM6sGbmjI/arcgis/rest/services/MC_CrashData_Master_2025/FeatureServer/0",
    date_field="Crash_Date",
    parse=parse,
    states=[8],
    bbox=(-109.1, 38.45, -107.6, 39.4),
    tz="America/Denver",
    page_size=2000,
    refresh_days=30,
    notes="Mesa County (Grand Junction area) only, 2018 through 2025; the service is named per year, so a "
          "newer year needs a new url. Hit-and-run flags are mostly empty before 2025.",
)
