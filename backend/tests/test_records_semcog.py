from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import semcog


def row(crash_id=3399001, **extra):
    raw = {"OBJECTID": 1, "CRASHID_UD10": crash_id, "DATE_FULL": "12/05/2025", "YEAR": 2025, "MONTH": 12, "DAY": 5,
           "HOUR": 21, "TIME_FULL": "2140", "PROPDAMG": 0, "KCOUNT": 0, "ACOUNT": 1, "BCOUNT": 1, "CCOUNT": 2,
           "TOTAL_INJURY": 4, "HIGH_SEVER": 2, "HITNRUN": 0, "WEATHER": 1, "LIGHTING": 4, "CRSHTYPEO": 2,
           "MAINROAD": "8 MILE", "INTERROAD": "WOODWARD", "XCORD": -83.1101, "YCORD": 42.4471,
           "cntname": "Wayne", "community": "Detroit", "_lon": -83.11012, "_lat": 42.44712}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["semcog"]
    assert spec is semcog.SPEC and spec.where == "YEAR >= 2021"


def test_parse_fields():
    r = semcog.parse(row())
    assert r["source_id"] == "3399001" and r["crash_datetime"] == datetime(2025, 12, 5, 21, 40)
    assert (r["latitude"], r["longitude"]) == (42.44712, -83.11012)
    assert r["injured"] == 4 and r["killed"] == 0 and r["severity"] == "Suspected Serious Injury"
    assert r["road"] == "8 MILE" and r["hit_and_run"] is False
    assert r["weather"] is None and r["lighting"] is None and r["crash_type"] is None


def test_fatal_unknown_time_and_hit_and_run():
    r = semcog.parse(row(KCOUNT=1, ACOUNT=0, BCOUNT=0, CCOUNT=0, HIGH_SEVER=1, TIME_FULL="UNK ", HOUR=None, HITNRUN=1))
    assert r["killed"] == 1 and r["injured"] == 0 and r["severity"] == "Fatal" and r["hit_and_run"] is True
    assert r["crash_datetime"] == datetime(2025, 12, 5, 0, 0)
    assert semcog.parse(row(DATE_FULL="2025-12-05"))["crash_datetime"] is None
    assert semcog.parse(row(HIGH_SEVER=None))["severity"] is None


def test_coordinates():
    r = semcog.parse(row(_lat=None, _lon=None))
    assert (r["latitude"], r["longitude"]) == (42.4471, -83.1101)
    r = semcog.parse(row(_lat=None, _lon=None, XCORD=None, YCORD=None))
    assert r["latitude"] is None and r["longitude"] is None
    assert semcog.parse(row(_lat=40.0, _lon=-83.1, XCORD=None))["latitude"] is None  # outside the region


def test_parse_all_skips_bad_rows():
    parsed, skipped = base.parse_all(semcog.SPEC, [row(), row(crash_id=None), row(crash_id=3399002, DATE_FULL=None)])
    assert [r["source_id"] for r in parsed] == ["3399001"] and skipped == 2
