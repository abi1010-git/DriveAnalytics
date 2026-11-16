"""Metro Nashville (Davidson County) "Traffic Accidents" (MNPD), ArcGIS Online
Traffic_Accidents_2/FeatureServer/0.

Checked Nov 2026 against the live service: 224,019 rows, one per crash (Accident_Number has
no duplicates), Date_and_Time from 2019-01-01 06:00 UTC to 2026-11-14 02:48 UTC (updated
daily). Accident_Number is published as a Double (e.g. 20260680824) and is stored as its
integer text. 2 rows lack coordinates. No license or copyright is stated in the service
metadata. maxRecordCount is 1000; the OID field is "ObjectId" (ordering by OBJECTID works,
the server matches field names case-insensitively).

Time convention: Date_and_Time is true UTC (epoch_is_local=False). The oldest value is
2019-01-01 06:00 UTC = local midnight CST, and the hour profile of 4,000 recent rows is lowest
at 07-10 UTC (1-4 am Central) and peaks at 19-23 UTC (afternoon/evening in Nashville).

Counts come from Number_of_Injuries / Number_of_Fatalities. There is no severity label, so
severity stays empty; weather, lighting and collision type use the *_Description fields.
"""
from ..base import SourceSpec, epoch, number, point, sane, text


def _id(value) -> str | None:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return text(value)


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("Lat"), raw.get("Long"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": _id(raw.get("Accident_Number")),
        "crash_datetime": sane(epoch(SPEC, raw.get("Date_and_Time")), earliest=2019),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("Street_Address")),
        "injured": number(raw.get("Number_of_Injuries")),
        "killed": number(raw.get("Number_of_Fatalities")),
        "severity": None,
        "primary_cause": None,
        "weather": text(raw.get("Weather_Description")),
        "lighting": text(raw.get("Illumination_Description")),
        "crash_type": text(raw.get("Collision_Type_Description")),
        "hit_and_run": {"Y": True, "N": False}.get(str(raw.get("Hit_and_Run") or "").strip().upper()),
    }


SPEC = SourceSpec(
    source="nashville",
    label="Nashville (Davidson County), TN crash reports",
    platform="arcgis",
    url="https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Traffic_Accidents_2/FeatureServer/0",
    date_field="Date_and_Time",
    parse=parse,
    states=[47],
    bbox=(-87.1, 35.93, -86.47, 36.45),
    tz="America/Chicago",
    page_size=1000,
    notes="From 2019; injury and death counts but no severity label.",
)
