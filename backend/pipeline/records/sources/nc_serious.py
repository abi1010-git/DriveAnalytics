"""NCDOT Traffic Safety Unit "NC FatalAndSeriousInjuryCrashes" (ArcGIS item a9125212cca34f2eb321de3bb0f1b7f2).

Statewide North Carolina, but FATAL (K) AND SERIOUS-INJURY (A) CRASHES ONLY; minor-injury and
property-damage crashes are not in this layer. Checked Nov 2026: 53,917 rows, one per crash
(Crash_ID unique, the id in NCDOT's statewide database), 2016 to 2025 (14,846 K, 39,071 A).
Updated annually as a rolling 10-year window (item last modified 2026-03-31), so a full reload
once a year is the natural cadence; older years drop out upstream.

Terms (item licenseInfo): for planning and prioritization only; about 97% of fatal crashes are
located; NCDOT is not liable for errors and the data "cannot be construed to be a legal
document".

Time: Date is TEXT "MM/DD/YYYY." (with a trailing period on every row) and Time is text "H:MM"
(24 h); both local Eastern time. Because Date is text, the loader's incremental filter
(`Date >= TIMESTAMP '...'`) silently matches 0 rows on this server, so incremental updates
return nothing: load this source with full=True only.

Counts: no injury or death counts are published (only K/A), so injured and killed stay empty.
severity = the publisher's own wording for the code: "Fatal (K)" / "Serious injury (A)".
Loader caveat: the object-id field is FID, and base._arcgis_pages orders by OBJECTID, which this
server rejects, so base.fetch needs an order-field option before this source can load.
"""
import re
from datetime import datetime

from ..base import SourceSpec, point, sane, text

_SEVERITY = {"K": "Fatal (K)", "A": "Serious injury (A)"}
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_TIME = re.compile(r"(\d{1,2}):(\d{2})")


def _when(raw: dict) -> datetime | None:
    found = _DATE.search(text(raw.get("Date")) or "")
    if not found:
        return None
    month, day, year = (int(g) for g in found.groups())
    hour = minute = 0
    clock = _TIME.fullmatch(text(raw.get("Time")) or "")
    if clock and int(clock.group(1)) <= 23 and int(clock.group(2)) <= 59:
        hour, minute = int(clock.group(1)), int(clock.group(2))
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("Latitude"), raw.get("Longitude"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("Crash_ID")),
        "crash_datetime": sane(_when(raw), earliest=2016),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("On_Road")),
        "injured": None,
        "killed": None,
        "severity": _SEVERITY.get(text(raw.get("Crash_Seve")) or ""),
        "primary_cause": None,
        "weather": text(raw.get("Weather")),
        "lighting": text(raw.get("Light_Cond")),
        "crash_type": text(raw.get("Crash_Type")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="nc_serious",
    label="North Carolina fatal & serious-injury crashes only (2016-2025)",
    platform="arcgis",
    url="https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NC_FatalAndSeriousInjuryCrashes/FeatureServer/0",
    date_field="Date",
    parse=parse,
    states=[37],
    bbox=(-84.4, 33.8, -75.4, 36.65),
    tz="America/New_York",
    page_size=2000,
    notes="Fatal (K) and serious-injury (A) crashes only, statewide, rolling 10 years updated annually. "
          "Date is text: incremental filters match nothing, use full reloads. Layer uses FID (OBJECTID ordering fails).",
    order_field="FID",
    incremental=False,
    refresh_days=30,
)
