"""Ohio DOT statewide crash locations, 2021-2025 (TIMS ArcGIS MapServer, one per year).

Checked Nov 2026: Safety/<year>_Crash_Locations/MapServer/0 for 2021-2025 (no other years
are published), identical fields in every year. One row per crash; DOCUMENT_NBR is unique in
each year (distinct count equals row count) and starts with the year. Rows: 2021 269,674;
2022 265,502; 2023 252,570; 2024 251,091; 2025 264,530 (CRASH_YR is 2025 in every row even
though the service description says "2024"). Every row has ODOT_LATITUDE_NBR/LONGITUDE_NBR.
No licence or terms are stated (copyrightText empty).

MONTH PRECISION ONLY: there is no date or day-of-month field, just CRASH_YR,
MONTH_OF_CRASH, DAY_IN_WEEK_CD and HOUR_OF_CRASH. crash_datetime is therefore the first day
of the crash month at 00:00; the hour is not attached to that made-up day. Any per-day or
per-hour analysis must exclude this source.

Updates: with no date field the loader's incremental filter (`date_field >= TIMESTAMP ...`)
cannot work. date_field is CRASH_YR so that an incremental run fails loudly (the server
answers "Unable to complete operation") instead of silently reading nothing; always load
this source with update(..., full=True), which re-reads all years (about 1.3M rows). That
is a yearly job: add each new <year>_Crash_Locations service to `urls` when ODOT publishes it.

Fields: severity is CRASH_SEVERITY_TXT ("Fatal", "Serious Injury Suspected", "Minor Injury
Suspected", "Injury Possible", "PDO/No Injury"); crash_type is CRASH_TYPE_TXT. There are no
injury or death counts, road names (NLFID is a route-inventory code), weather, lighting,
cause or hit-and-run fields, so those columns stay empty.
"""
from datetime import datetime

from ..base import SourceSpec, number, point, sane, text

BASE = "https://tims.dot.state.oh.us/ags/rest/services/Safety"
URLS = [f"{BASE}/{year}_Crash_Locations/MapServer/0" for year in range(2021, 2026)]


def _month(raw: dict) -> datetime | None:
    year, month = number(raw.get("CRASH_YR")), number(raw.get("MONTH_OF_CRASH"))
    if year is None or month is None or not 1 <= month <= 12:
        return None
    return datetime(year, month, 1)


def parse(raw: dict) -> dict | None:
    doc = number(raw.get("DOCUMENT_NBR"))
    lat, lon = point(SPEC, raw.get("ODOT_LATITUDE_NBR"), raw.get("ODOT_LONGITUDE_NBR"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": str(doc) if doc else None,
        "crash_datetime": sane(_month(raw)),
        "latitude": lat,
        "longitude": lon,
        "road": None,
        "injured": None,
        "killed": None,
        "severity": text(raw.get("CRASH_SEVERITY_TXT")),
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("CRASH_TYPE_TXT")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="ohio",
    label="Ohio DOT crash locations",
    platform="arcgis",
    url=URLS[-1],
    urls=URLS,
    date_field="CRASH_YR",
    parse=parse,
    states=[39],
    bbox=(-85.0, 38.2, -80.3, 42.4),
    tz="America/New_York",
    page_size=2000,
    notes="Month precision only (crash_datetime = 1st of the month, 00:00). No injury counts or "
          "road names. No date field, so incremental updates fail: reload yearly with full=True.",
    incremental=False,
    refresh_days=30,
)
