"""Knoxville Regional TPO "Crashes" (ArcGIS item 21d076d95f524a13adf774d4f4b28e0f).

Checked Nov 2026: 209,171 rows, one per crash, 2015-01-01 to 2026-09-30, covering the Knoxville
TPO planning area (Knox 66%, Blount, Anderson, Loudon, parts of Sevier and Roane). The layer is
republished by script (item snippet: "between Jan 1, 2015 and Sep 30, 2026"), so expect quarterly-
ish refreshes. No license or terms are stated on the item (TERMS unconfirmed).

Id strategy (risk): the layer has no crash or report number, only OBJECTID and GlobalID, both
regenerated when the layer is republished. source_id is therefore built from
local date+time (minute), the published GPS coordinates (5 dp) and a short hash of Total_Vehicles,
Manner_of_First_Collision, First_Harmful_Event, Route and Log_Mile. On the full file this
collides for 62 groups (8 of them byte-identical duplicate rows), i.e. ~0.03% of crashes would be
merged. If the publisher later corrects any of those fields (e.g. adds a time to a 2026 crash
that is now at 00:00, or moves its coordinates), the crash gets a new id and the old row stays
behind as a duplicate; a periodic full reload into a cleared source is the remedy.

Time: Date_of_Crash is true UTC (midnight local shows as 04:00/05:00 UTC; evening peak sits at
21-23 UTC). Most 2026 rows are at local midnight, i.e. date only (no time yet).

Counts: Total_Injured is NOT an injury count (property-damage-only crashes mostly carry 1-3), so
injured = Total_Suspected_Serious_Injuries + Total_Other_Injuries; killed = Total_Fatalities;
severity = Type_of_Crash (KABCO label, e.g. "(B) Suspected Minor Injury"). Person-level packed
arrays (Person_Age, Person_Type, Driver_Age, Safety_Equipment, ...) are deliberately ignored.
"""
import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..base import SourceSpec, number, point, sane, text

_ID_FIELDS = ("Total_Vehicles", "Manner_of_First_Collision", "First_Harmful_Event", "Route", "Log_Mile")


def _when(raw: dict) -> datetime | None:
    try:
        moment = datetime.fromtimestamp(int(raw.get("Date_of_Crash")) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return moment.astimezone(ZoneInfo(SPEC.tz)).replace(tzinfo=None)


def _coord(value) -> str:
    try:
        return f"{float(value):.5f}"
    except (TypeError, ValueError):
        return "na"


def crash_id(raw: dict, when: datetime | None) -> str | None:
    if when is None:
        return None
    digest = hashlib.sha1(json.dumps([raw.get(k) for k in _ID_FIELDS], default=str).encode()).hexdigest()[:10]
    return f"{when:%Y%m%d%H%M}_{_coord(raw.get('Gps_Coordinate_Latitude'))}_{_coord(raw.get('Gps_Coordinate_Longitude'))}_{digest}"


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in ("Total_Suspected_Serious_Injuries", "Total_Other_Injuries")]
    counts = [c for c in counts if c is not None]
    return sum(counts) if counts else None


def parse(raw: dict) -> dict | None:
    when = sane(_when(raw), earliest=2015)
    lat, lon = point(SPEC, raw.get("Gps_Coordinate_Latitude"), raw.get("Gps_Coordinate_Longitude"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": crash_id(raw, when),
        "crash_datetime": when,
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("Road_Name")),
        "injured": _injured(raw),
        "killed": number(raw.get("Total_Fatalities")),
        "severity": text(raw.get("Type_of_Crash")),
        "primary_cause": None,
        "weather": text(raw.get("Weather_Conditions")),
        "lighting": text(raw.get("Light_Conditions")),
        "crash_type": text(raw.get("Manner_of_First_Collision")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="knoxville",
    label="Knoxville, TN region (Knoxville TPO area) crash reports",
    platform="arcgis",
    url="https://services2.arcgis.com/Gypl21NmiWS1cM7h/arcgis/rest/services/Crashes/FeatureServer/0",
    date_field="Date_of_Crash",
    parse=parse,
    states=[47],
    bbox=(-84.6, 35.5, -83.4, 36.35),
    tz="America/New_York",
    page_size=1000,
    notes="No crash id published: source_id is derived from date/time, coordinates and crash fields "
          "(~0.03% merged; corrections upstream create duplicates). Recent rows are often date-only.",
)
