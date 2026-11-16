from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import kansas as ks


def row(key="20269990001", day=1794204000000, hour="16", **extra):
    raw = {"OBJECTID": 1, "ACCIDENT_KEY": key, "DATE_OF_ACCIDENT": day, "ACC_HOUR": hour, "ACC_SEVERITY": "INJURY",
           "MOST_SERIOUS_INJURY": "I", "FATALITIES": 0, "DISABLING_INJURIES": 1, "NON_INCAPACITATING_INJURIES": 2,
           "POSSIBLE_INJURIES": 1, "CWOV_FHE_ACC_TYPE": "REAR END", "ACCIDENT_CLASS_FHE_DESC": "COLL W OTHER MOTOR VEHICLE",
           "WEATHER_CONDITIONS_DESC": "NO ADVERSE CONDITIONS", "LIGHT_CONDITIONS_DESC": "DAYLIGHT",
           "DRIVER_CIRCUMSTANCE": "INATTENTION - GENERAL", "LATITUDE": 39.01, "LONGITUDE": -94.69, "_lat": 39.0101, "_lon": -94.6901}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["kansas"]
    assert spec is ks.SPEC and spec.page_size == 10000 and "2019-01-01" in spec.where


def test_parse_fields():
    r = ks.parse(row())
    assert r["source_id"] == "20269990001"
    assert r["crash_datetime"] == datetime(2026, 11, 9, 16, 0)  # 06:00 UTC = local midnight CST, plus ACC_HOUR
    assert r["injured"] == 4 and r["killed"] == 0 and r["severity"] == "INJURY"
    assert (r["latitude"], r["longitude"]) == (39.0101, -94.6901)
    assert r["crash_type"] == "REAR END" and r["primary_cause"] == "INATTENTION - GENERAL"
    assert r["weather"] == "NO ADVERSE CONDITIONS" and r["lighting"] == "DAYLIGHT"
    assert r["road"] is None and r["hit_and_run"] is None


def test_dates_in_daylight_time_and_fallbacks():
    assert ks.parse(row(day=1791262800000, hour="07"))["crash_datetime"] == datetime(2026, 10, 6, 7, 0)  # CDT
    assert ks.parse(row(hour=None))["crash_datetime"] == datetime(2026, 11, 9, 0, 0)
    assert ks.parse(row(day=None))["crash_datetime"] is None
    r = ks.parse(row(CWOV_FHE_ACC_TYPE=None, _lat=None, _lon=None))
    assert r["crash_type"] == "COLL W OTHER MOTOR VEHICLE" and r["latitude"] == 39.01
    assert ks.parse(row(DISABLING_INJURIES=None, NON_INCAPACITATING_INJURIES=None, POSSIBLE_INJURIES=None))["injured"] is None


def test_fetch_filters_and_collapses_repeated_rows(tmp_path):
    seen = []
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 3}
        seen.append(query)
        return {"features": [{"attributes": row("A"), "geometry": {"x": -97.3, "y": 37.6}},
                             {"attributes": row("A"), "geometry": {"x": -97.3, "y": 37.6}},
                             {"attributes": row("B"), "geometry": {"x": -97.3, "y": 37.6}}]}
    path = base.fetch(ks.SPEC, datetime(2026, 10, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(ks.SPEC, base.iter_raw(path))
    assert sorted(r["source_id"] for r in parsed) == ["A", "B"] and skipped == 0
    assert "DATE_OF_ACCIDENT >= TIMESTAMP '2019-01-01 00:00:00'" in seen[0]["where"][0]
    assert "DATE_OF_ACCIDENT >= TIMESTAMP '2026-10-01 00:00:00'" in seen[0]["where"][0]
