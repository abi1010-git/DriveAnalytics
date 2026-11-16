"""Vermont crashes behind the VTrans Public Crash Query Tool (ArcGIS Online "CrashPQT").

Checked Nov 2026: 182,980 rows, 2010-01-01 to 2026-11-13 14:17, current to within two days.
Mostly one row per crash: 568 REPORTNUMBER values appear twice (1,136 rows, almost all from
2019-2020). Sampled pairs are the same crash (same time and place), either identical rows or
the same report filed under two State Police barracks ids, so the loader's per-id collapse
(last row wins) is used and no `reduce`. 3,022 rows have no coordinates. Some report numbers
carry leading spaces (" 19-04169"); they are trimmed. Terms: public item owned by an individual
ArcGIS Online account (mlofgren); no license or access information stated.

Time: ACCIDENTDATE carries date and time; there is no separate time field. It is local wall
time stored "as UTC" (epoch_is_local=True). Evidence: DayNight is "Day" for exactly UTC-clock
hours 06-18 and "Night" for 19-05 in all ~1,240 June-July 2025 rows (if the clock were true UTC,
"Day" would cover 02:00-14:00 local); November rows agree (07:50 Day, 18:25 Night), and crashes
peak at clock hours 12-16. The TIMESTAMP filter is accepted and compares local to local.
Some times carry seconds (e.g. 18:16:33); they are kept as published.

Fields: there are no injury or death counts, only InjuryType ("Fatal", "Injury", "Property
Damage Only"), stored as severity; injured/killed stay empty. road is RDFLNAME, else
STREETADDRESS; crash_type is DirOfCollision (direction of collision, e.g. "Rear End"); weather is
Weather. DayNight is derived from the clock hour, not lighting conditions, so lighting stays
empty. Impairment and Involving (pedestrian, bicycle, heavy truck...) have no column and are not
loaded. No hit-and-run field.
"""
from ..base import SourceSpec, epoch, point, sane, text

UNKNOWN = {"unknown", "null", "none"}


def _label(value) -> str | None:
    value = text(value)
    return None if value is None or value.lower() in UNKNOWN else value


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("REPORTNUMBER")),
        "crash_datetime": sane(epoch(SPEC, raw.get("ACCIDENTDATE"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("RDFLNAME")) or text(raw.get("STREETADDRESS")),
        "injured": None,
        "killed": None,
        "severity": _label(raw.get("InjuryType")),
        "primary_cause": None,
        "weather": _label(raw.get("Weather")),
        "lighting": None,
        "crash_type": _label(raw.get("DirOfCollision")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="vermont",
    label="VTrans crash reports (Vermont)",
    platform="arcgis",
    url="https://services1.arcgis.com/NXmBVyW5TaiCXqFs/arcgis/rest/services/CrashPQT/FeatureServer/0",
    date_field="ACCIDENTDATE",
    parse=parse,
    states=[50],
    bbox=(-73.6, 42.6, -71.3, 45.1),
    tz="America/New_York",
    page_size=2000,
    epoch_is_local=True,
    notes="Statewide from 2010 (about 183k crashes). Severity is a crash type only (Fatal/Injury/"
          "Property Damage Only); no injury or death counts, no lighting or hit-and-run field.",
)
