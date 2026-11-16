from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import cleveland


def row(doc=20259990001, **extra):
    raw = {"OBJECTID_1": 1, "OBJECTID": 77, "DOCUMENT_NBR": doc, "CRASH_YR": 2025, "Crash_Date": "2025-12-31",
           "HOUR_OF_CRASH": 17, "CRASH_SEVERITY_CD": 3, "CRASH_TYPE_CD": 2, "INCAPAC_INJURIES_NBR": 1,
           "NON_INCAPAC_INJURIES_NBR": 2, "POSSIBLE_INJURIES_NBR": 1, "NO_INJURY_REPORTED_NBR": 3,
           "ODPS_TOTAL_FATALITIES_NBR": 0, "ODOT_LATITUDE_NBR": 41.4801, "ODOT_LONGITUDE_NBR": -81.6802,
           "ODPS_LOC_ROAD_NME": "Superior", "ODPS_LOC_ROAD_SUFFIX_CD": "AVE", "LIGHT_COND_PRIMARY_CD": 3,
           "WEATHER_COND_CD": 6, "U1_AGE_NBR": 40, "U1_GENDER_CD": "F", "_lat": 41.4801, "_lon": -81.6802}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["cleveland"]
    assert spec is cleveland.SPEC and spec.order_field == "OBJECTID_1" and spec.refresh_days == 30


def test_parse_hour_precision_and_labels():
    r = cleveland.parse(row())
    assert r["source_id"] == "20259990001" and r["crash_datetime"] == datetime(2025, 12, 31, 17, 0)
    assert r["injured"] == 4 and r["killed"] == 0  # NO_INJURY_REPORTED_NBR left out
    assert r["severity"] == "Minor Injury" and r["crash_type"] == "Rear End"
    assert r["lighting"] == "Dark - Lighted Roadway" and r["weather"] == "Snow" and r["road"] == "Superior AVE"
    assert r["primary_cause"] is None


def test_date_variants_and_bounds():
    assert cleveland.parse(row(Crash_Date=1767139200000, HOUR_OF_CRASH=0))["crash_datetime"] == datetime(2025, 12, 31)
    assert cleveland.parse(row(HOUR_OF_CRASH=None))["crash_datetime"] is None
    assert cleveland.parse(row(Crash_Date="2015-06-01"))["crash_datetime"] is None  # before 2019
    assert cleveland.parse(row(CRASH_SEVERITY_CD=42))["severity"] is None
    assert cleveland.parse(row(ODOT_LATITUDE_NBR=0, ODOT_LONGITUDE_NBR=0, _lat=None, _lon=None))["latitude"] is None


def test_fetch_orders_by_objectid_1(tmp_path):
    seen = []
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 1}
        seen.append(query)
        return {"features": [{"attributes": row(), "geometry": {"x": -81.68, "y": 41.48}}]}
    path = base.fetch(cleveland.SPEC, None, raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(cleveland.SPEC, base.iter_raw(path))
    assert seen[0]["orderByFields"] == ["OBJECTID_1"] and seen[0]["where"] == ["(CRASH_YR >= 2019)"]
    assert len(parsed) == 1 and skipped == 0
