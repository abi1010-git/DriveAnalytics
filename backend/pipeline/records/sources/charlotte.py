"""Charlotte CDOT "TCLS Crashes" (ArcGIS MapServer CDOT/TCLS_Crashes/0, City of Charlotte).

Checked Nov 2026 against the live service: 555,120 rows from 2010-01-01, newest 2026-11-10
19:56 local; 310,596 rows from 2019 (2019: 38,376; 2020: 29,345; 2021: 38,560; 2022: 44,268;
2023: 44,472; 2024: 43,384; 2025: 36,173; 2026: 36,018). One row per crash: CRSH_ID is unique
from 2019 (group-by/having check), CASE_NUM is never empty. Bounded to 2019+ with
DATE_VAL_YEAR (a 4-digit text year, so the text comparison is safe). No license or terms
are stated on the service.

Time: DATE_VAL is true UTC epoch ms (epoch_is_local stays False). The service also publishes
MILT_TIME (local "HHMM") and DATE_VAL_DAY: 1794358560000 is 2026-11-11 00:56 UTC with
MILT_TIME "1956" and day 10 (19:56 EST); 1575229560000 is 2019-12-01 19:46 UTC with "1446".

Coordinates: LATITUDE/LONGITUDE and the geometry agree up to Aug 2026 (>99% usable each
month), but from September 2026 nearly every row's coordinates are broken at the publisher
(usable: Sep 110 of 3,943; Oct 85 of 3,729; Nov 14 of 1,112). Broken ones are stored WITHOUT
a location:
- 11,051 rows (Aug 2025 - Nov 2026) have a positive longitude. It is not just a lost minus
  sign: the values span 80.29-80.65 while genuine Charlotte longitudes span -81.05 to -80.57,
  so negating them would misplace crashes; they are dropped by the bbox instead.
- 1,047 rows since mid-October 2025 carry tiny values (about 0.0035, -0.0081).
Also note a gap at the source: Nov 2025 has 783 crashes and Dec 2025 321 (vs ~3,500 normally).

Fields: severity is CRSH_LEVL_DESC ("Property Damage", "Possible Injury", "Non Serious
Injury", "Serious injury", "fatality"); crash_type is CRASH_TYPE. There are no injury or death
counts, no road name, cause, weather or lighting fields, so those stay empty.
"""
from ..base import SourceSpec, epoch, point, sane, text


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("CRSH_ID")),
        "crash_datetime": sane(epoch(SPEC, raw.get("DATE_VAL")), earliest=2019),
        "latitude": lat,
        "longitude": lon,
        "road": None,
        "injured": None,
        "killed": None,
        "severity": text(raw.get("CRSH_LEVL_DESC")),
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("CRASH_TYPE")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="charlotte",
    label="Charlotte, NC (CDOT) crash reports",
    platform="arcgis",
    url="https://gis.charlottenc.gov/arcgis/rest/services/CDOT/TCLS_Crashes/MapServer/0",
    date_field="DATE_VAL",
    parse=parse,
    states=[37],
    bbox=(-81.08, 34.98, -80.53, 35.53),
    tz="America/New_York",
    where="DATE_VAL_YEAR >= '2019'",
    page_size=2000,
    notes="From 2019. Severity level and crash type only; no injury counts. Since Sep 2026 nearly all rows "
          "have broken coordinates at the source and are stored without a location. Nov-Dec 2025 mostly missing.",
)
