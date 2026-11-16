"""UDOT "Utah Crash Locations" (ArcGIS, one layer per year: 0 = 2026 back to 7 = 2019).

Checked Nov 2026: 463,569 rows across the 8 layers (2026: 49,611; 2025: 59,860; 2024: 59,316;
2023: 59,882; 2022: 58,806; 2021: 61,141; 2020: 50,409; 2019: 64,544), newest 2026-11-11
14:09 local, oldest 2019-01-01. Refreshed nightly; personal information removed. One row per
crash: crash_id is unique in every layer except 2019, where 100 ids appear twice as rows
identical apart from OBJECTID (the loader's per-id collapse keeps one). Every row has a
point. No license or terms are stated on the service.

Time: crash_datetime is an esriFieldTypeTimestampOffset field, so the service returns it as
an ISO string with an offset ("2026-11-11T21:09:33+00:00"), not epoch milliseconds; parse()
converts it itself. The values are true UTC (epoch_is_local stays False): every year layer
starts near 07:00 UTC on Jan 1 and ends near 06:59 UTC on Dec 31, i.e. local midnight in
Mountain Standard Time. There is no separate time text field to cross-check. The loader's
TIMESTAMP filter works on this field.

Fields: injured = number_two + number_three + number_four injuries (possible, suspected minor,
suspected serious). number_one_injuries counts people with no injury: "No Injury/PDO" crashes
carry only that count (88,900 of them in 2025), so it is left out. killed is
number_fatalities; severity is crash_severity_desc. There is no single cause field (only
yes/no flags such as dui, speed_related), so primary_cause stays empty.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from ..base import SourceSpec, epoch, number, point, sane, text

LAYERS = "https://services.arcgis.com/pA2nEVnB6tquxgOW/arcgis/rest/services/Utah_Crash_Locations/FeatureServer"
INJURY_COUNTS = ("number_two_injuries", "number_three_injuries", "number_four_injuries")


def _when(value) -> datetime | None:
    """ISO string with offset (timestampOffset fields) or epoch ms -> naive Mountain time."""
    if isinstance(value, str) and not value.lstrip("-").isdigit():
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if moment.tzinfo is None:
            return None
        return moment.astimezone(ZoneInfo(SPEC.tz)).replace(tzinfo=None)
    return epoch(SPEC, value)


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in INJURY_COUNTS]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def parse(raw: dict) -> dict | None:
    crash_id = number(raw.get("crash_id"))
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(crash_id) if crash_id else None,
        "crash_datetime": sane(_when(raw.get("crash_datetime"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("main_road_name")),
        "injured": _injured(raw),
        "killed": number(raw.get("number_fatalities")),
        "severity": text(raw.get("crash_severity_desc")),
        "primary_cause": None,
        "weather": text(raw.get("weather_condition_desc")),
        "lighting": text(raw.get("light_condition_desc")),
        "crash_type": text(raw.get("manner_collision_desc")),
        "hit_and_run": {"Y": True, "N": False}.get(raw.get("hit_and_run")),
    }


SPEC = SourceSpec(
    source="utah",
    label="Utah DOT crash reports",
    platform="arcgis",
    url=f"{LAYERS}/0",
    urls=[f"{LAYERS}/{layer}" for layer in range(8)],  # 2026, 2025, ... 2019
    date_field="crash_datetime",
    parse=parse,
    states=[49],
    bbox=(-114.2, 36.9, -108.9, 42.1),
    tz="America/Denver",
    page_size=2000,
    notes="Statewide from 2019, one service layer per year; a new year's layer must be added to `urls`. "
          "No primary-cause field.",
)
