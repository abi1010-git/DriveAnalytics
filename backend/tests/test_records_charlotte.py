from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import charlotte


def row(cid="1300001", when=1794358560000, **extra):  # 2026-11-11 00:56 UTC = 19:56 EST on the 10th
    raw = {"OBJECTID": 1, "CRSH_ID": cid, "DATE_VAL": when, "DATE_VAL_YEAR": "2026", "DATE_VAL_DAY": "10",
           "MILT_TIME": "1956", "CASE_NUM": "20261110195699", "CRSH_TYPE_CD": 21, "CRASH_TYPE": "Rear end; slow or stop",
           "CRSH_LEVL": 4, "CRSH_LEVL_DESC": "Possible Injury", "LATITUDE": 35.2201, "LONGITUDE": -80.8402,
           "_lat": 35.2201, "_lon": -80.8402}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["charlotte"]
    assert spec is charlotte.SPEC and not spec.epoch_is_local and "2019" in spec.where


def test_parse_utc_epoch_to_local():
    r = charlotte.parse(row())
    assert r["source_id"] == "1300001" and r["crash_datetime"] == datetime(2026, 11, 10, 19, 56)  # matches MILT_TIME
    assert r["severity"] == "Possible Injury" and r["crash_type"] == "Rear end; slow or stop"
    assert r["injured"] is None and r["killed"] is None and r["road"] is None
    assert (r["latitude"], r["longitude"]) == (35.2201, -80.8402)
    assert charlotte.parse(row(when=1262304000000))["crash_datetime"] is None  # 2009/2010, before the bound


def test_coordinate_faults():
    positive = charlotte.parse(row(LATITUDE=35.0528, LONGITUDE=80.5116, _lat=35.0528, _lon=80.5116))
    assert positive["latitude"] is None and positive["longitude"] is None  # not a plain sign flip: not repaired
    scaled = charlotte.parse(row(LATITUDE=0.00352208, LONGITUDE=-0.00808162, _lat=0.0035, _lon=-0.0081))
    assert scaled["latitude"] is None and scaled["longitude"] is None
    assert charlotte.parse(row(LATITUDE=None, LONGITUDE=None))["latitude"] == 35.2201  # geometry fallback
    assert charlotte.parse(row(LATITUDE=40.7, LONGITUDE=74.0, _lat=None, _lon=None))["latitude"] is None


def test_fetch_and_parse(tmp_path):
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 2}
        assert query["orderByFields"] == ["OBJECTID"]
        return {"features": [{"attributes": row("1"), "geometry": {"x": -80.84, "y": 35.22}},
                             {"attributes": row("2", CRSH_LEVL_DESC=None), "geometry": None}]}
    path = base.fetch(charlotte.SPEC, datetime(2026, 11, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(charlotte.SPEC, base.iter_raw(path))
    assert sorted(r["source_id"] for r in parsed) == ["1", "2"] and skipped == 0
