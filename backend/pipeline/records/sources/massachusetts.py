"""MassDOT open crash data, statewide Massachusetts (ArcGIS, one service per year).

Checked Nov 2026 on gis.crashdata.dot.mass.gov (layer 0 "Crash" = one row per crash; layers 1/2
are vehicles and persons and are not read). Years and row counts:
  2026 105,731 (2026-01-01 to 2026-11-14 14:06, i.e. current to the day before checking)
  2025 130,896 | 2024 135,406 | 2023 135,326 | 2022 134,472 | 2021 125,212   (total 767,043)
The 2023 service is named MASSDOT_ODP_OPEN_2023v (MASSDOT_ODP_OPEN_2023 returns 404), and
no service exists for 2020 or earlier in this folder. CRASH_NUMB is unique within every year
(groupBy/having count > 1 returned nothing) and numbers increase across years. CRASH_STATUS
is "Open"/"Open Fatal" for 2025 and 2026 (preliminary, may still change; the 3-day overlap and
upsert pick up later edits only within that window) and "Closed" for 2021-2023. About 4-7% of
rows per year have no LAT/LON (and no geometry); those load without coordinates. No license
or terms are stated on the services (copyrightText and description empty).

Time: CRASH_DATETIME is local wall time stored "as UTC" (epoch_is_local=True), although the
service declares dateFieldsTimeReference UTC. Evidence: its UTC clock equals the text fields
CRASH_DATE_TEXT/CRASH_TIME_2 (e.g. "11 14 2026" "2:06 PM" -> 14:06) for November (EST) and
July (EDT) rows in 2021-2026 alike. The loader's TIMESTAMP filter is accepted and compares
local to local.

Fields: severity is CRASH_SEVERITY_DESCR as published ("Fatal injury", "Non-fatal injury",
"Property damage only (none injured)"); "Unknown"/"Not Reported" are left empty. injured is
NUMB_NONFATAL_INJR, killed is NUMB_FATAL_INJR. road is RDWY (e.g. "Union St Rte N / ..."),
crash_type MANR_COLL_DESCR, weather WEATH_COND_DESCR (may list two conditions "Clear/Cloudy"),
lighting AMBNT_LIGHT_DESCR, hit_and_run HIT_RUN_DESCR. DRVR_CNTRB_CIRC_CL lists every
driver's circumstances, not one primary cause, so primary_cause stays empty.
"""
from ..base import SourceSpec, epoch, number, point, sane, text

BASE = "https://gis.crashdata.dot.mass.gov/arcgis/rest/services/MassDOT/MASSDOT_ODP_OPEN_{}/FeatureServer/0"
YEARS = ("2026", "2025", "2024", "2023v", "2022", "2021")
UNKNOWN = {"unknown", "not reported", "reported but invalid", "not applicable"}
HIT_RUN = {"Yes, hit and run": True, "No hit and run": False}


def _label(value) -> str | None:
    value = text(value)
    return None if value is None or value.lower() in UNKNOWN else value


def parse(raw: dict) -> dict | None:
    numb = number(raw.get("CRASH_NUMB"))
    lat, lon = point(SPEC, raw.get("LAT"), raw.get("LON"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(numb) if numb else None,
        "crash_datetime": sane(epoch(SPEC, raw.get("CRASH_DATETIME"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("RDWY")),
        "injured": number(raw.get("NUMB_NONFATAL_INJR")),
        "killed": number(raw.get("NUMB_FATAL_INJR")),
        "severity": _label(raw.get("CRASH_SEVERITY_DESCR")),
        "primary_cause": None,
        "weather": _label(raw.get("WEATH_COND_DESCR")),
        "lighting": _label(raw.get("AMBNT_LIGHT_DESCR")),
        "crash_type": _label(raw.get("MANR_COLL_DESCR")),
        "hit_and_run": HIT_RUN.get(text(raw.get("HIT_RUN_DESCR"))),
    }


SPEC = SourceSpec(
    source="massachusetts",
    label="MassDOT crash reports (Massachusetts)",
    platform="arcgis",
    url=BASE.format(YEARS[0]),
    urls=[BASE.format(year) for year in YEARS],
    date_field="CRASH_DATETIME",
    parse=parse,
    states=[25],
    bbox=(-73.6, 41.1, -69.8, 43.0),
    tz="America/New_York",
    page_size=2000,
    epoch_is_local=True,
    notes="Statewide from 2021 (about 767k crashes), one service per year; add the next year's "
          "MASSDOT_ODP_OPEN_<year> to YEARS each January (2023's is named 2023v). Current and previous "
          "year rows are preliminary (CRASH_STATUS Open). About 5% of crashes have no coordinates.",
)
