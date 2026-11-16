from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import iowa


def row(key=20261572673.0, when=1794503460000, **extra):
    # 1794503460000 = 2026-11-12 17:11 "as UTC"; Iowa publishes local wall time this way
    raw = {"OBJECTID": 1, "CRASH_KEY": key, "CRASH_DATE": 1794441600000, "TIMESTR": "17:11", "CRASH_DATETIME": when,
           "SYSTEMSTR": "77", "LITERAL": "340TH AVE AND US 30 W", "CSEV": 3, "FATALITIES": 0, "INJURIES": 3,
           "MAJINJURY": 1, "MININJURY": 1, "POSSINJURY": 1, "UNKINJURY": 0, "MAJCSE": 24, "WEATHER": 2, "LIGHT": 2,
           "CRCOMNNR": 3, "_lon": -90.4323, "_lat": 41.8155}
    raw.update(extra)
    return raw


def test_registered():
    assert records.all_specs()["iowa"] is iowa.SPEC


def test_parse_fields_and_local_time():
    r = iowa.parse(row())
    assert r["source_id"] == "20261572673"
    assert r["crash_datetime"] == datetime(2026, 11, 12, 17, 11)  # equals TIMESTR, not shifted to Central
    assert (r["latitude"], r["longitude"]) == (41.8155, -90.4323)
    assert r["injured"] == 3 and r["killed"] == 0 and r["severity"] == "Minor Injury"
    assert r["primary_cause"] == "Followed too close" and r["crash_type"] == "Rear-end (front to rear)"
    assert r["weather"] == "Cloudy" and r["lighting"] == "Dusk" and r["hit_and_run"] is None
    assert r["road"] == "340TH AVE AND US 30 W"


def test_route_fatal_and_missing_codes():
    r = iowa.parse(row(SYSTEMSTR="I-80", CSEV=1, FATALITIES=2, MAJINJURY=0, MININJURY=0, POSSINJURY=0,
                       WEATHER=77, LIGHT=None, MAJCSE=72))
    assert r["road"] == "I-80" and r["severity"] == "Fatal" and r["killed"] == 2 and r["injured"] == 0
    assert r["weather"] is None and r["lighting"] is None and r["primary_cause"] is None


def test_bad_coordinates_and_dates():
    r = iowa.parse(row(_lat=0, _lon=0))
    assert r["latitude"] is None and r["longitude"] is None
    assert iowa.parse(row(when=None))["crash_datetime"] is None
    assert iowa.parse(row(key=None))["source_id"] is None


def test_identical_duplicate_rows_collapse():
    parsed, skipped = base.parse_all(iowa.SPEC, [row(), row(OBJECTID=2), row(key=20261572674.0), row(when=None)])
    assert sorted(r["source_id"] for r in parsed) == ["20261572673", "20261572674"] and skipped == 1
