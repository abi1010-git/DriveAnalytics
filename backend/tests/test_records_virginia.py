from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import virginia


def row(doc=262430146, day=1788148800000, tm=933, **extra):
    # 1788148800000 = 2026-08-31 04:00 UTC = local midnight (EDT); the time is in CRASH_MILITARY_TM
    raw = {"OBJECTID": 1, "DOCUMENT_NBR": doc, "CRASH_DT": day, "CRASH_MILITARY_TM": tm, "CRASH_SEVERITY": "B",
           "K_PEOPLE": 0, "A_PEOPLE": 1, "B_PEOPLE": 1, "C_PEOPLE": 0, "PERSONS_INJURED": 2, "COLLISION_TYPE": "1",
           "WEATHER_CONDITION": "5", "LIGHT_CONDITION": "2", "HITRUN_NOT_HITRUN": "0",
           "ROUTE_OR_STREET_NM": "400 OLIVER HILL WAY", "RTE_NM": "R-VA   US00360PA001",
           "LAT": 37.53808053015, "LON": -77.42426312993, "_lat": 37.53808053, "_lon": -77.42426313}
    raw.update(extra)
    return raw


def test_registered_with_2019_window():
    spec = records.all_specs()["virginia"]
    assert spec is virginia.SPEC and "2019-01-01" in spec.where


def test_parse_fields():
    r = virginia.parse(row())
    assert r["source_id"] == "262430146"
    assert r["crash_datetime"] == datetime(2026, 8, 31, 9, 33)
    assert (r["latitude"], r["longitude"]) == (37.53808053015, -77.42426312993)
    assert r["injured"] == 2 and r["killed"] == 0 and r["severity"] == "Visible Injury"
    assert r["crash_type"] == "Rear End" and r["weather"] == "Rain" and r["lighting"] == "Daylight"
    assert r["hit_and_run"] is False and r["road"] == "400 OLIVER HILL WAY" and r["primary_cause"] is None


def test_dates_in_standard_time_and_bad_clock():
    winter = 1483246800000  # 2017-01-01 05:00 UTC = local midnight (EST)
    assert virginia.parse(row(day=winter, tm=0))["crash_datetime"] == datetime(2017, 1, 1, 0, 0)
    assert virginia.parse(row(day=winter, tm=2359))["crash_datetime"] == datetime(2017, 1, 1, 23, 59)
    assert virginia.parse(row(tm=None))["crash_datetime"] == datetime(2026, 8, 31)
    assert virginia.parse(row(tm=1275))["crash_datetime"] == datetime(2026, 8, 31)
    assert virginia.parse(row(day=None))["crash_datetime"] is None


def test_fatal_codes_and_fallbacks():
    r = virginia.parse(row(CRASH_SEVERITY="K", K_PEOPLE=2, A_PEOPLE=0, B_PEOPLE=0, HITRUN_NOT_HITRUN="1",
                           WEATHER_CONDITION="0", LIGHT_CONDITION="99", COLLISION_TYPE="12", ROUTE_OR_STREET_NM=None))
    assert r["severity"] == "Fatal Injury" and r["killed"] == 2 and r["injured"] == 0 and r["hit_and_run"] is True
    assert r["weather"] is None and r["lighting"] is None and r["crash_type"] == "Ped"
    assert r["road"] == "R-VA US00360PA001"


def test_coordinates_fall_back_to_geometry_and_bbox():
    assert virginia.parse(row(LAT=None, LON=None))["latitude"] == 37.53808053
    r = virginia.parse(row(LAT=0, LON=0, _lat=None, _lon=None))
    assert r["latitude"] is None and r["longitude"] is None


def test_where_is_combined_with_since(tmp_path):
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return {"features": [{"attributes": row()}, {"attributes": row(OBJECTID=2)}]}
    path = base.fetch(virginia.SPEC, datetime(2026, 8, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(virginia.SPEC, base.iter_raw(path))
    where = calls[0]["where"][0]
    assert "CRASH_DT >= TIMESTAMP '2019-01-01 00:00:00'" in where and "TIMESTAMP '2026-08-01 00:00:00'" in where
    assert len(parsed) == 1 and skipped == 0
