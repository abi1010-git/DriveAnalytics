"""Cleveland, OH crashes 2012-2025 (ODOT-derived; ArcGIS Online
Cleveland_Crashes_2012_to_2025_(Public_View)/FeatureServer/0).

Checked Nov 2026 against the live service: 184,612 rows, 2012-01-01 to 2025-12-31; 87,583
from 2019 (2019: 15,670; 2020: 14,112; 2021: 15,030; 2022: 14,689; 2023: 11,947; 2024:
7,677; 2025: 8,458 - the drop from 2023 is in the published data). A static, closed
dataset (no 2026 rows); incremental updates work on Crash_Date but find nothing new, so
refresh_days=30. One row per crash: DOCUMENT_NBR (the ODPS crash document number) is unique and
never null. The object-id field is OBJECTID_1 (an unrelated integer OBJECTID also exists).
Every row from 2019 has ODOT_LATITUDE_NBR/ODOT_LONGITUDE_NBR. No license is stated.

Time: Crash_Date is an esriFieldTypeDateOnly field returned as "YYYY-MM-DD" (day precision,
no time; the TIMESTAMP filter works on it). HOUR_OF_CRASH (0-23, never null from 2019) gives
the local hour, so crash_datetime = date + hour:00 (hour precision, minutes unknown).

Fields: severity, crash_type, weather and lighting are the layer's own coded-value domain
labels (copied below from the service's domains). injured = INCAPAC_INJURIES_NBR +
NON_INCAPAC_INJURIES_NBR + POSSIBLE_INJURIES_NBR (NO_INJURY_REPORTED_NBR counts uninjured
people and is excluded); killed = ODPS_TOTAL_FATALITIES_NBR. The U1_/U2_ unit fields
(ages, sex of drivers) are deliberately not stored.
"""
from datetime import datetime, timedelta, timezone

from ..base import SourceSpec, number, point, sane, text

SEVERITY = {1: "Fatal", 2: "Serious Injury", 3: "Minor Injury", 4: "Possible Injury", 5: "Property Damage Only"}
CRASH_TYPE = {0: "Unknown", 1: "Head On", 2: "Rear End", 3: "Backing", 4: "Sideswipe - Meeting",
              5: "Sideswipe - Passing", 6: "Angle", 7: "Parked Vehicle", 8: "Pedestrian", 9: "Animal", 10: "Train",
              11: "Pedalcycles", 12: "Other Non-Vehicle", 13: "Fixed Object", 14: "Other Object", 16: "Overturning",
              17: "Other Non-Collision", 18: "Left Turn", 19: "Right Turn"}
LIGHT = {1: "Daylight", 2: "Dawn/Dusk", 3: "Dark - Lighted Roadway", 4: "Dark - Roadway Not Lighted",
         5: "Dark - Unknown Roadway Lighting", 9: "Other / Unknown"}
WEATHER = {1: "Clear", 2: "Cloudy", 3: "Fog, Smog, Smoke", 4: "Rain", 5: "Sleet, Hail", 6: "Snow",
           7: "Severe Crosswinds", 8: "Blowing Sand, Soil, Dirt, Snow", 9: "Other / Unknown", 99: "Unknown"}
INJURY_COUNTS = ("INCAPAC_INJURIES_NBR", "NON_INCAPAC_INJURIES_NBR", "POSSIBLE_INJURIES_NBR")


def _when(raw: dict) -> datetime | None:
    value, hour = raw.get("Crash_Date"), number(raw.get("HOUR_OF_CRASH"))
    if isinstance(value, str):
        try:
            day = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None
    else:  # older servers return date-only values as epoch ms of UTC midnight
        try:
            day = datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    if day is None or hour is None or hour > 23:
        return None
    return day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hour)


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in INJURY_COUNTS]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def _road(raw: dict) -> str | None:
    name = text(raw.get("ODPS_LOC_ROAD_NME"))
    return text(f"{name} {raw.get('ODPS_LOC_ROAD_SUFFIX_CD') or ''}") if name else None


def parse(raw: dict) -> dict | None:
    document = number(raw.get("DOCUMENT_NBR"))
    lat, lon = point(SPEC, raw.get("ODOT_LATITUDE_NBR"), raw.get("ODOT_LONGITUDE_NBR"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(document) if document else None,
        "crash_datetime": sane(_when(raw), earliest=2019),
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": _injured(raw),
        "killed": number(raw.get("ODPS_TOTAL_FATALITIES_NBR")),
        "severity": SEVERITY.get(number(raw.get("CRASH_SEVERITY_CD"))),
        "primary_cause": None,
        "weather": WEATHER.get(number(raw.get("WEATHER_COND_CD"))),
        "lighting": LIGHT.get(number(raw.get("LIGHT_COND_PRIMARY_CD"))),
        "crash_type": CRASH_TYPE.get(number(raw.get("CRASH_TYPE_CD"))),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="cleveland",
    label="Cleveland, OH crash reports (ODOT)",
    platform="arcgis",
    url="https://services3.arcgis.com/dty2kHktVXHrqO8i/arcgis/rest/services/Cleveland_Crashes_2012_to_2025_(Public_View)/FeatureServer/0",
    date_field="Crash_Date",
    parse=parse,
    states=[39],
    bbox=(-81.89, 41.38, -81.52, 41.62),
    tz="America/New_York",
    order_field="OBJECTID_1",
    where="CRASH_YR >= 2019",
    page_size=2000,
    refresh_days=30,
    notes="2019-2025, closed dataset (no 2026). Hour precision: the time is the hour of the crash.",
)
