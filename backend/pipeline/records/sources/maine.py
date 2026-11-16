"""MaineDOT crash locations, 10 years plus current year (ArcGIS Online hosted view, layer 44).

Checked Nov 2026: 361,430 rows, 2016-01-01 to 2026-11-12 19:22 local, one row per crash.
CRASH_ID (e.g. "2026-30473") is unique (groupBy/having count > 1 returned nothing);
REPORT_NUMBER is NOT unique (agency numbers like "16-664-AC" repeat), so it is not used as the
id. The item says the source layer is "updated weekly on Sunday" (last refresh 2026-11-15).
Only 4 rows lack coordinates. Terms: owner MaineDOT.IT, public item; licenseInfo is a GIS
accuracy/"assume responsibility" disclaimer, no license restricting reuse.

The service name contains "Test_View" (Crashes_Attributes_10_Year_and_Current_Year_Test_View):
it is the view the public MaineDOT crash map uses today, but the name suggests it may be
renamed or replaced; if requests start failing, look for the current view of the item
"MaineDOT Crash Locations - 10 Years Complete". Being a rolling 10-year window, the oldest year
drops out each January (rows already loaded stay).

Time: ACCIDENT_DATE_TIME is true UTC (epoch_is_local=False). Evidence: converted to New York it
equals the text field ACCIDENT_TIME and ACCIDENT_HOUR for Nov 2026 and Jan 2019 rows (EST, +5h)
and Jul 2025 rows (EDT, +4h). The TIMESTAMP filter is accepted; on this hosted service it
is read as UTC, so incremental reads start 4-5 hours earlier than asked (harmless overlap).

Fields: severity is the KABCO code INJURY_LEVEL (K/A/B/C/PD) spelled out with standard KABCO
names. INJURY_COUNT equals K+A+B+C in every row (checked by query), so injured = A+B+C (K
excluded) and killed = NO_OF_K_INJ. road is PRIMARY_ROUTE_NAME (e.g. "ST RTE 222"; local roads
show inventory codes like "RD INV 21 00484"), crash_type TYPE_OF_CRASH_DESCR, weather and
lighting their *_DESCR fields. Driver actions are per unit, not a primary cause; no hit-and-run
field.
"""
from ..base import SourceSpec, epoch, number, point, sane, text

SEVERITY = {"K": "Fatal (K)", "A": "Suspected Serious Injury (A)", "B": "Suspected Minor Injury (B)",
            "C": "Possible Injury (C)", "PD": "Property Damage Only"}


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in ("NO_OF_A_INJ", "NO_OF_B_INJ", "NO_OF_C_INJ")]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def _label(value) -> str | None:
    value = text(value)
    return None if value is None or value.lower() == "unknown" else value


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("CRASH_ID")),
        "crash_datetime": sane(epoch(SPEC, raw.get("ACCIDENT_DATE_TIME"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("PRIMARY_ROUTE_NAME")),
        "injured": _injured(raw),
        "killed": number(raw.get("NO_OF_K_INJ")),
        "severity": SEVERITY.get(text(raw.get("INJURY_LEVEL")) or ""),
        "primary_cause": None,
        "weather": _label(raw.get("WEATHER_CONDITION_DESCR")),
        "lighting": _label(raw.get("LIGHT_CONDITION_DESCR")),
        "crash_type": _label(raw.get("TYPE_OF_CRASH_DESCR")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="maine",
    label="MaineDOT crash reports (Maine)",
    platform="arcgis",
    url="https://services1.arcgis.com/RbMX0mRVOFNTdLzd/arcgis/rest/services/"
        "Crashes_Attributes_10_Year_and_Current_Year_Test_View/FeatureServer/44",
    date_field="ACCIDENT_DATE_TIME",
    parse=parse,
    states=[23],
    bbox=(-71.2, 42.9, -66.8, 47.5),
    tz="America/New_York",
    page_size=2000,
    notes="Statewide rolling 10 years plus current year (about 361k crashes from 2016), refreshed weekly. "
          "The service is a view named '..._Test_View' and may be renamed; no hit-and-run field.",
)
