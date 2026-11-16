from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import massachusetts as ma


def row(numb=5731280, when=1794665160000, **extra):
    # 1794665160000 = 2026-11-14 14:06 "as UTC"; MassDOT stores local wall time this way
    raw = {"OBJECTID": 1, "CRASH_NUMB": numb, "CRASH_DATE_TEXT": "11 14 2026", "CRASH_TIME_2": "2:06 PM",
           "CRASH_DATETIME": when, "CRASH_STATUS": "Open", "CRASH_SEVERITY_DESCR": "Non-fatal injury",
           "MAX_INJR_SVRTY_CL": "Suspected Minor Injury (B)", "NUMB_FATAL_INJR": 0, "NUMB_NONFATAL_INJR": 3,
           "RDWY": " Union St Rte N  / Union  Rte S", "MANR_COLL_DESCR": "Rear-end", "WEATH_COND_DESCR": "Clear/Cloudy",
           "AMBNT_LIGHT_DESCR": "Daylight", "HIT_RUN_DESCR": "No hit and run", "LAT": 42.71883426,
           "LON": -71.16802966, "_lat": 42.71884, "_lon": -71.16803}
    raw.update(extra)
    return raw


def test_registered_with_year_services():
    spec = records.all_specs()["massachusetts"]
    assert spec is ma.SPEC and len(spec.urls) == 6 and spec.epoch_is_local
    assert any("MASSDOT_ODP_OPEN_2023v" in u for u in spec.urls) and spec.url == spec.urls[0]


def test_parse_fields_and_local_time():
    r = ma.parse(row())
    assert r["source_id"] == "5731280"
    assert r["crash_datetime"] == datetime(2026, 11, 14, 14, 6)  # equals CRASH_TIME_2, not shifted
    assert (r["latitude"], r["longitude"]) == (42.71883426, -71.16802966)
    assert r["injured"] == 3 and r["killed"] == 0 and r["severity"] == "Non-fatal injury"
    assert r["road"] == "Union St Rte N / Union Rte S" and r["crash_type"] == "Rear-end"
    assert r["weather"] == "Clear/Cloudy" and r["lighting"] == "Daylight" and r["hit_and_run"] is False
    assert r["primary_cause"] is None


def test_summer_time_is_not_shifted():
    assert ma.parse(row(when=1783444500000))["crash_datetime"] == datetime(2026, 7, 7, 17, 15)


def test_fatal_hit_and_run_and_unknown_labels():
    r = ma.parse(row(CRASH_SEVERITY_DESCR="Fatal injury", NUMB_FATAL_INJR=2, NUMB_NONFATAL_INJR=1,
                     HIT_RUN_DESCR="Yes, hit and run", WEATH_COND_DESCR="Unknown", AMBNT_LIGHT_DESCR="Not reported",
                     MANR_COLL_DESCR=None))
    assert r["killed"] == 2 and r["injured"] == 1 and r["severity"] == "Fatal injury" and r["hit_and_run"] is True
    assert r["weather"] is None and r["lighting"] is None and r["crash_type"] is None
    assert ma.parse(row(CRASH_SEVERITY_DESCR="Unknown"))["severity"] is None


def test_coordinates_fallback_and_bad_values():
    r = ma.parse(row(LAT=None, LON=None))
    assert (r["latitude"], r["longitude"]) == (42.71884, -71.16803)
    r = ma.parse(row(LAT=0.0, LON=0.0, _lat=None, _lon=None))
    assert r["latitude"] is None and r["longitude"] is None
    assert ma.parse(row(when=None))["crash_datetime"] is None
    parsed, skipped = base.parse_all(ma.SPEC, [row(), row(numb=None), row(numb=5731281)])
    assert sorted(r["source_id"] for r in parsed) == ["5731280", "5731281"] and skipped == 1
