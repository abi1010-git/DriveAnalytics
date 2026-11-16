"""Denver "Traffic Accidents" (Denver Police Department, NIBRS-based), ArcGIS Online
ODC_CRIME_TRAFFICACCIDENTS5YR_P/FeatureServer/325.

Checked Nov 2026 against the live service: 295,097 rows, first_occurrence_date from
2013-01-01 00:00 to 2026-11-11 19:46 (as stored). Rows are per offense: almost every
incident_id has one row, but some repeat (e.g. one 2021 incident appears 8 times, identical;
another twice with SERIOUSLY_INJURED null on one row and 1 on the other), so `reduce` merges
rows of one incident. Copyright "City and County of Denver, Denver Police Department"; the
service description says the data is dynamic and will be replaced by a revised traffic
dataset by the end of Q4 2026 (field changes possible). No license is stated in the service.

LOADER INCOMPATIBILITY (not fixed here, base.py untouched): the layer's OID field is
"object_id" and the server rejects orderByFields=OBJECTID ("'OBJECTID' parameter is
invalid"), which base._arcgis_pages always sends, so fetch() fails for this source until the
loader can order by the layer's own OID field. The service is also slow (~30-60 s a page).

Time convention: first_occurrence_date stores local wall time as if it were UTC
(epoch_is_local=True). The oldest value is exactly 2013-01-01 00:00, and the hour profile of
1,000 recent rows peaks at 15-17 h and is lowest at 3-4 h as stored; read as true UTC that
would put the busiest hours at 8-10 am and the quietest at 8-9 pm Mountain time.

Counts: injured is SERIOUSLY_INJURED (the only injury count published: serious injuries
only, minor injuries are not counted), killed is FATALITIES; both are null on ~9% of rows
(mostly hit-and-run reports). severity is top_traffic_accident_offense, the source's own
label ("TRAF - ACCIDENT", "... - SBI", "... - FATAL", "... - HIT & RUN", "... - DUI/DUID",
"... - POLICE"); hit_and_run is True only when that label says so (otherwise unknown).
"""
from ..base import SourceSpec, epoch, number, point, sane, text


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("geo_lat"), raw.get("geo_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    label = text(raw.get("top_traffic_accident_offense"))
    return {
        "source_id": text(raw.get("incident_id")),
        "crash_datetime": sane(epoch(SPEC, raw.get("first_occurrence_date")), earliest=2013),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("incident_address")),
        "injured": number(raw.get("SERIOUSLY_INJURED")),
        "killed": number(raw.get("FATALITIES")),
        "severity": label,
        "primary_cause": text(raw.get("TU1_DRIVER_HUMANCONTRIBFACTOR")),
        "weather": None,
        "lighting": text(raw.get("LIGHT_CONDITION")),
        "crash_type": text(raw.get("HARMFUL_EVENT_SEQ_1")),
        "hit_and_run": True if label and "HIT & RUN" in label else None,
    }


def reduce(rows: list[dict]) -> dict:
    """Rows of one incident repeat the same crash: keep the first value present for each
    column and the largest injury/death count (never a sum, which would double count)."""
    merged = dict(rows[0])
    for key in merged:
        if merged[key] is None:
            merged[key] = next((r[key] for r in rows if r.get(key) is not None), None)
    for key in ("injured", "killed"):
        counts = [r[key] for r in rows if r.get(key) is not None]
        merged[key] = max(counts) if counts else None
    if any(r.get("hit_and_run") for r in rows):
        merged["hit_and_run"] = True
    return merged


SPEC = SourceSpec(
    source="denver",
    label="Denver, CO police traffic accident reports",
    platform="arcgis",
    url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_CRIME_TRAFFICACCIDENTS5YR_P/FeatureServer/325",
    date_field="first_occurrence_date",
    parse=parse,
    states=[8],
    bbox=(-105.15, 39.58, -104.56, 39.95),
    tz="America/Denver",
    page_size=2000,
    order_field="object_id",  # this layer names its object-id field differently
    epoch_is_local=True,
    reduce=reduce,
    notes="Serious injuries only; severity is the offense label. Dataset to be replaced by end of Q4 2026.",
)
