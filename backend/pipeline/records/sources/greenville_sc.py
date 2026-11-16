"""GPATS (Greenville-Pickens Area Transportation Study MPO) "2017 to 2025 GPATS Crash Data"
(ArcGIS item 4bc1d05d6a9848049ca8b2132fe3d91f), SCDOT crash reports for the MPO area.

Checked Nov 2026: 188,597 rows, one per crash (Crash_Number unique), 2017-01-01 to 2025-12-31;
a static, cleaned spreadsheet export ("Created from 2017to2025GPATS_CrashDataCleaned.xlsx on
7/31/2026"), so no new rows arrive until the MPO republishes. Counties: Greenville 83%, Pickens,
Anderson, Spartanburg, Laurens. The MPO boundary changed in 2023: areas removed were dropped
entirely and areas added have no data before 2020, so this loader keeps Crash_Date >= 2021
(103,145 rows) where the footprint is consistent.

TERMS unconfirmed: the item states no license or access terms; GPATS's guidance is to contact
them about use of the data. Confirm before redistributing.

Time: Crash_Date is true UTC holding local midnight (04:00/05:00 UTC); the time of day comes from
the text field Time_ ("1:30 PM", always present). Time_of_Crash is an Excel-style time-on-a-
dummy-date and is ignored.

Counts: injured = F__of_Injuries, killed = F__of_Fatalities, severity = Max_Injury_Code
(e.g. "Possible Injury", "Fatal"). Light_Condition and Road_Surface_Condition were simplified by
the publisher to Daylight/Night and Dry/Wet.

Loader caveat: this layer's object-id field is FID, not OBJECTID; base._arcgis_pages orders by
OBJECTID, which this server rejects ("'OBJECTID' parameter is invalid"), so base.fetch needs an
order-field option before this source can load.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..base import SourceSpec, number, point, sane, text


def _when(raw: dict) -> datetime | None:
    try:
        moment = datetime.fromtimestamp(int(raw.get("Crash_Date")) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    day = moment.astimezone(ZoneInfo(SPEC.tz)).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    clock = text(raw.get("Time_"))
    if clock:
        try:
            parsed = datetime.strptime(clock.upper(), "%I:%M %p")
            return day.replace(hour=parsed.hour, minute=parsed.minute)
        except ValueError:
            pass
    return day


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("Latitude"), raw.get("Longitude"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("Crash_Number")),
        "crash_datetime": sane(_when(raw), earliest=2017),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("SMS_Main_Street_Name")),
        "injured": number(raw.get("F__of_Injuries")),
        "killed": number(raw.get("F__of_Fatalities")),
        "severity": text(raw.get("Max_Injury_Code")),
        "primary_cause": text(raw.get("Probable_Cause")),
        "weather": None,
        "lighting": text(raw.get("Light_Condition")),
        "crash_type": text(raw.get("Manner_of_Collision")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="greenville_sc",
    label="Greenville-Pickens, SC area (GPATS) crash reports, 2021-2025",
    platform="arcgis",
    url="https://services3.arcgis.com/bjOyhhlaaCIcmO3H/arcgis/rest/services/2017_to_2025_GPATS_Crash_Data/FeatureServer/0",
    date_field="Crash_Date",
    parse=parse,
    states=[45],
    bbox=(-82.85, 34.5, -82.0, 35.25),
    tz="America/New_York",
    where="Crash_Date >= TIMESTAMP '2021-01-01 00:00:00'",
    page_size=2000,
    notes="Static 2017-2025 export, loaded from 2021 (MPO boundary change). Terms unconfirmed (contact GPATS). "
          "Layer uses FID, so OBJECTID ordering in base.fetch fails.",
    order_field="FID",
    refresh_days=30,
)
