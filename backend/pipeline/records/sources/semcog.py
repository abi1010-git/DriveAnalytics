"""SEMCOG crash locations for Southeast Michigan, 2021-2025 (ArcGIS crash2025_10year).

Checked Nov 2026: 1,324,813 rows for 2016-2025, one per crash (CRASHID_UD10 distinct count
equals row count); `where` keeps YEAR >= 2021, 642,897 rows (2021 124,631; 2022 128,821;
2023 131,448; 2024 129,853; 2025 128,144). Seven counties: Wayne (incl. Detroit), Oakland,
Macomb, Washtenaw, Livingston, Monroe, St. Clair. Published once a year as a 10-year
window; the next edition will be a new service to swap into `url`.

Terms: the item says "By using this data, you agree to the SEMCOG Copyright License
Agreement" (maps-semcog.opendata.arcgis.com/pages/copyright-license-agreement, text last
updated 2020). Section 1(a) grants a perpetual, non-exclusive, royalty-free licence to use,
reproduce, distribute, publish and display the works, with no non-commercial limit. Section
2(a) requires SEMCOG's copyright notice in a reasonably prominent position wherever the
data is shown; that notice's own wording ("Reproduction or Use Without Permission is
Prohibited") conflicts with the grant, so attribution must be shown and the wording
reviewed before publishing.

Time: there are no date fields. DATE_FULL is text "MM/DD/YYYY" and TIME_FULL text "HHMM",
local Michigan time, in every row from 2021; 650 rows have TIME_FULL "UNK " (and HOUR empty),
and those keep the date at 00:00. Because the loader's incremental filter needs a date
field, date_field is YEAR so an incremental run fails loudly ("Unable to perform query")
rather than silently reading nothing (`DATE_FULL >= TIMESTAMP ...` returns 0 rows); always
load with update(..., full=True).

Coordinates: the layer is stored in EPSG:2898, but the WGS84 geometry (outSR=4326) is used;
XCORD/YCORD already hold longitude/latitude and are the fallback. 579 rows have no location.

Fields: HIGH_SEVER is the crash's KABCO level (1-5); it matched the count fields exactly
(1 iff KCOUNT > 0, 2 iff no K and ACOUNT > 0, ... 5 iff PROPDAMG = 1), and the labels below
are the standard Michigan UD-10 names for those levels. injured is ACOUNT + BCOUNT + CCOUNT
(TOTAL_INJURY also counts deaths); killed is KCOUNT. road is MAINROAD. WEATHER, LIGHTING and
CRSHTYPEO are unlabelled integer codes with no published domain, so they stay empty.
"""
from datetime import datetime

from ..base import SourceSpec, number, point, sane, text

SEVERITY = {1: "Fatal", 2: "Suspected Serious Injury", 3: "Suspected Minor Injury", 4: "Possible Injury",
            5: "No Injury (Property Damage Only)"}


def _when(raw: dict) -> datetime | None:
    try:
        day = datetime.strptime(str(raw.get("DATE_FULL")).strip(), "%m/%d/%Y")
    except ValueError:
        return None
    clock = str(raw.get("TIME_FULL") or "").strip()
    if len(clock) == 4 and clock.isdigit() and int(clock[:2]) < 24 and int(clock[2:]) < 60:
        return day.replace(hour=int(clock[:2]), minute=int(clock[2:]))
    return day


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in ("ACOUNT", "BCOUNT", "CCOUNT")]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def parse(raw: dict) -> dict | None:
    crash_id = number(raw.get("CRASHID_UD10"))
    lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("YCORD"), raw.get("XCORD"))
    severity = number(raw.get("HIGH_SEVER"))
    return {
        "source_id": str(crash_id) if crash_id else None,
        "crash_datetime": sane(_when(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("MAINROAD")),
        "injured": _injured(raw),
        "killed": number(raw.get("KCOUNT")),
        "severity": SEVERITY.get(severity) if severity is not None else None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": None,
        "hit_and_run": {1: True, 0: False}.get(number(raw.get("HITNRUN"))),
    }


SPEC = SourceSpec(
    source="semcog",
    label="Southeast Michigan (SEMCOG) crash reports",
    platform="arcgis",
    url="https://services1.arcgis.com/xUx8EjNc6egUPYWh/arcgis/rest/services/crash2025_10year/FeatureServer/0",
    date_field="YEAR",
    where="YEAR >= 2021",
    parse=parse,
    states=[26],
    bbox=(-84.4, 41.6, -82.3, 43.4),
    tz="America/Detroit",
    page_size=2000,
    notes="Seven SE Michigan counties, 2021-2025. Requires the SEMCOG copyright notice wherever shown "
          "(licence allows redistribution). No date field: reload with full=True.",
    incremental=False,
    refresh_days=30,
)
