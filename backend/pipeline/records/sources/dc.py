"""Washington, DC "Crashes in DC" (DDOT / MPD), ArcGIS MapServer layer 24 on maps2.dcgis.dc.gov.

Checked Nov 2026 against the live service: 357,330 rows, one per crash (CRIMEID has no
duplicates; CCN repeats on ~650 rows, so it is not used as the id). Newest REPORTDATE
2026-11-13 21:20 UTC; 1,378 rows have no date and ~370 carry junk years (1825-1827, 1900,
2000-2007). Real coverage starts in 2008 (2,658 rows) and is complete from 2009, so the
server-side filter keeps REPORTDATE >= 2008-01-01 and sane() drops anything still odd.
Before ~2015 REPORTDATE is a date only (local midnight). Copyright "District Department of
Transportation"; no license is stated in the service metadata. maxRecordCount is 1000.

Time convention: REPORTDATE is true UTC (epoch_is_local=False). Date-only rows sit at
04:00/05:00 UTC, i.e. local midnight under EDT/EST, and the hour profile of 4,000 recent rows
is lowest at 06-09 UTC (1-5 am Eastern) and peaks at 19-21 UTC (afternoon rush in DC).

Injuries are per road-user mode (driver, passenger, pedestrian, bicyclist, other) in
major/minor/unknown buckets: injured is the sum of all of them, killed the sum of the FATAL*
columns. There is no severity label, cause, weather or lighting field, so those stay empty.
"""
import re

from ..base import SourceSpec, epoch, number, point, sane, text

INJURY_FIELDS = tuple(f"{kind}INJURIES_{mode}" for kind in ("MAJOR", "MINOR", "UNKNOWN")
                      for mode in ("BICYCLIST", "DRIVER", "PEDESTRIAN")) + \
    tuple(f"{kind}INJURIES{mode}" for kind in ("MAJOR", "MINOR", "UNKNOWN") for mode in ("PASSENGER", "OTHER"))
FATAL_FIELDS = ("FATAL_BICYCLIST", "FATAL_DRIVER", "FATAL_PEDESTRIAN", "FATALPASSENGER", "FATALOTHER")

_CITY_SUFFIX = re.compile(r"\s*WASHINGTON,?\s*$", re.IGNORECASE)


def _total(raw: dict, fields) -> int | None:
    values = [number(raw.get(f)) for f in fields]
    values = [v for v in values if v is not None]
    return sum(values) if values else None


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    road = text(raw.get("ADDRESS"))
    return {
        "source_id": text(raw.get("CRIMEID")),
        "crash_datetime": sane(epoch(SPEC, raw.get("REPORTDATE")), earliest=2008),
        "latitude": lat,
        "longitude": lon,
        "road": text(_CITY_SUFFIX.sub("", road)) if road else None,
        "injured": _total(raw, INJURY_FIELDS),
        "killed": _total(raw, FATAL_FIELDS),
        "severity": None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": None,
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="dc",
    label="Washington, DC crash reports",
    platform="arcgis",
    url="https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Safety_WebMercator/MapServer/24",
    date_field="REPORTDATE",
    parse=parse,
    states=[11],
    bbox=(-77.15, 38.78, -76.89, 39.01),
    tz="America/New_York",
    where="REPORTDATE >= DATE '2008-01-01'",
    page_size=1000,
    notes="Injury and death counts per road-user mode; no severity label. Date only before ~2015.",
)
