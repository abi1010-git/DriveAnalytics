"""Connecticut crashes from the UConn Connecticut Crash Data Repository dashboard service.

TERMS NOT CONFIRMED: this is the ArcGIS backend of the CTCDR public dashboards
(gis.cti.uconn.edu, copyrightText "CTDOT, UConn, CTSRC"), not a documented open-data API. The
repository's website has its own terms of use and asks users to register for downloads; check
them (or ask CTSRC at UConn) before loading this source into anything shared or public.

Checked Nov 2026: layer 0 "Crash" (layers 1/2 are persons and vehicles) holds 1,224,689 rows,
2015-01-01 to 2026-11-13 16:38 local, one row per crash: CrashID is unique (groupBy/having
count > 1 returned nothing). 2026 holds 59,260 crashes against about 103k in each of 2024 and
2025, so recent months are still filling in as reports arrive. The SPEC `where` bounds the load
to CrashDate >= 2019-01-01 (767,781 rows) to keep the first load moderate; drop it for 2015-2018.
Coordinates come from the point geometry (no lat/lon fields), merged as _lat/_lon.

Time: CrashDate is returned as true UTC (epoch_is_local=False). The layer declares
dateFieldsTimeReference America/New_York, so the server converts its local values to UTC on
output: the UTC clock minus CrashTimeHour was 4h for every row on 1-2 Jul 2025 (681 rows) and
5h for every row on 10-11 Jan 2025 (533 rows). The TIMESTAMP filter is accepted and read in
New York time (CrashDate >= TIMESTAMP '2026-11-13 16:00:00' finds the 16:38 crash, 17:00 does
not), which matches the local `since` the loader builds.

Fields: there are no injury or death counts on the crash layer, so injured/killed stay empty.
severity is MostSevereInjury (KABCO, e.g. "Suspected Minor Injury (B)"), else CrashSeverity
("Fatal (Kill)", "Injury of any type ...", "Property Damage Only"). road is NameOfRoadway (routes
look like "15-N"), crash_type MannerOfCrashCollisionImpact, weather WeatherCondition, lighting
LightCondition; "Unknown"/"Not Applicable"/"Other" are left empty. No cause or hit-and-run field.
"""
from ..base import SourceSpec, epoch, number, point, sane, text

UNKNOWN = {"unknown", "not applicable", "other"}


def _label(value) -> str | None:
    value = text(value)
    return None if value is None or value.lower() in UNKNOWN else value


def parse(raw: dict) -> dict | None:
    crash_id = number(raw.get("CrashID"))
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(crash_id) if crash_id else None,
        "crash_datetime": sane(epoch(SPEC, raw.get("CrashDate"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("NameOfRoadway")),
        "injured": None,
        "killed": None,
        "severity": text(raw.get("MostSevereInjury")) or text(raw.get("CrashSeverity")),
        "primary_cause": None,
        "weather": _label(raw.get("WeatherCondition")),
        "lighting": _label(raw.get("LightCondition")),
        "crash_type": _label(raw.get("MannerOfCrashCollisionImpact")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="connecticut",
    label="Connecticut Crash Data Repository (Connecticut)",
    platform="arcgis",
    url="https://gis.cti.uconn.edu/arcgis/rest/services/Crash_Dashboards/ConnecticutCrash/FeatureServer/0",
    date_field="CrashDate",
    parse=parse,
    states=[9],
    bbox=(-73.8, 40.9, -71.7, 42.1),
    tz="America/New_York",
    where="CrashDate >= TIMESTAMP '2019-01-01 00:00:00'",
    page_size=2000,
    notes="TERMS NOT CONFIRMED: dashboard backend of the UConn CT Crash Data Repository, not a documented "
          "open-data API; check CTCDR terms before sharing. Loaded from 2019 (about 768k crashes; the service "
          "goes back to 2015). Recent months fill in late. No injury or death counts.",
)
