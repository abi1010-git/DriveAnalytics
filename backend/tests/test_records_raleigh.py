from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import raleigh


def row(key=397001, when=1794576480000, hour=13, **extra):
    # 1794576480000 = 2026-11-13 13:28 "as UTC"; newer Raleigh rows hold local wall time this way
    raw = {"OBJECTID": 1, "key_crash": key, "DateOfCrash": when, "Crash_Date_Hour": hour, "LocalUse": "P26000001           ",
           "LocationCity": "RALEIGH                       ", "LocationRoadNameOn": "GLENWOOD AVE          ",
           "FirstHarmfulEvent": "Rear end, slow or stop", "WeatherCondition1": "Rain", "killed": 0,
           "type_a_injury": 1, "type_b_injury": 0, "type_c_injury": 2, "no_injury": 1,
           "LocationLatitude": 35.8001, "LocationLongitude": -78.6502, "_lat": 35.80012, "_lon": -78.65021}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["raleigh"]
    assert spec is raleigh.SPEC and spec.states == [37] and spec.platform == "arcgis"


def test_parse_fields():
    r = raleigh.parse(row())
    assert r["source_id"] == "397001"
    assert r["crash_datetime"] == datetime(2026, 11, 13, 13, 28)
    assert (r["latitude"], r["longitude"]) == (35.80012, -78.65021)  # geometry first
    assert r["injured"] == 3 and r["killed"] == 0 and r["severity"] is None
    assert r["road"] == "GLENWOOD AVE" and r["crash_type"] == "Rear end, slow or stop" and r["weather"] == "Rain"
    assert r["lighting"] is None and r["hit_and_run"] is None


def test_older_rows_are_true_utc():
    # 1560623400000 = 2019-06-15 18:30 UTC = 14:30 EDT, and Crash_Date_Hour says 14
    assert raleigh.parse(row(when=1560623400000, hour=14))["crash_datetime"] == datetime(2019, 6, 15, 14, 30)
    assert raleigh.parse(row(when=1560623400000, hour=None))["crash_datetime"] == datetime(2019, 6, 15, 14, 30)
    assert raleigh.parse(row(when=None))["crash_datetime"] is None


def test_missing_counts_and_coordinates():
    r = raleigh.parse(row(killed=None, type_a_injury=None, type_b_injury=None, type_c_injury=None, WeatherCondition1=""))
    assert r["injured"] is None and r["killed"] is None and r["weather"] is None
    r = raleigh.parse(row(_lat=None, _lon=None))
    assert r["latitude"] == 35.8001
    r = raleigh.parse(row(_lat=None, _lon=None, LocationLatitude=79.1, LocationLongitude=-35.8))
    assert r["latitude"] is None and r["longitude"] is None


def test_incremental_filter(tmp_path):
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return {"features": [{"attributes": row()}, {"attributes": row(key=397002)}]}
    path = base.fetch(raleigh.SPEC, datetime(2026, 11, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(raleigh.SPEC, base.iter_raw(path))
    assert "DateOfCrash >= TIMESTAMP '2026-11-01 00:00:00'" in calls[0]["where"][0]
    assert len(parsed) == 2 and skipped == 0
