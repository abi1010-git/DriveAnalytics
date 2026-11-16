from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import allegheny


def old_row(crn="2024900001", **extra):  # 2021-2024 schema
    raw = {"_id": 1, "CRASH_CRN": crn, "CRASH_COUNTY": "02", "CRASH_YEAR": 2024, "CRASH_MONTH": "03", "DAY_OF_WEEK": 2,
           "TIME_OF_DAY": "1715", "HOUR_OF_DAY": "17", "FATAL_COUNT": 0, "INJURY_COUNT": 3, "TOT_INJ_COUNT": 3,
           "MAJ_INJ_COUNT": 1, "MIN_INJ_COUNT": 1, "MAX_SEVERITY_LEVEL": 2, "DEC_LAT": 40.4401, "DEC_LONG": -79.9902,
           "LATITUDE": "40 26:24.360", "STREET_NAME": "FORBES AVE", "DRIVER_COUNT_16YR": 1}
    raw.update(extra)
    return raw


def new_row(crn=2025900001, **extra):  # 2025 schema
    raw = {"_id": 1, "CRN": crn, "COUNTY": "02", "CRASH_YEAR": 2025, "CRASH_MONTH": 11, "DAY_OF_WEEK": 6,
           "TIME_OF_DAY": 2150, "HOUR_OF_DAY": 21, "FATAL_COUNT": 1, "INJURY_COUNT": 2, "SUSP_SERIOUS_INJ_COUNT": 1,
           "SUSP_MINOR_INJ_COUNT": 1, "POSSIBLE_INJ_COUNT": 0, "MAX_SEVERITY_LEVEL": 1, "DEC_LATITUDE": 40.5001,
           "DEC_LONGITUDE": -80.0502}
    raw.update(extra)
    return raw


def test_registered_non_incremental():
    spec = records.all_specs()["allegheny"]
    assert spec is allegheny.SPEC and not spec.incremental and spec.refresh_days == 30
    assert spec.id_field == "_id" and len(spec.urls) == 5 and spec.urls[-1] == "c6bedb17-2d23-49b1-843a-8f6b41e5e5c3"


def test_parse_both_schemas_month_precision():
    old = allegheny.parse(old_row())
    assert old["source_id"] == "2024900001" and old["crash_datetime"] == datetime(2024, 3, 1)
    assert old["injured"] == 3 and old["killed"] == 0 and old["severity"] == "Suspected serious injury"
    assert (old["latitude"], old["longitude"]) == (40.4401, -79.9902) and old["road"] == "FORBES AVE"
    new = allegheny.parse(new_row())
    assert new["source_id"] == "2025900001" and new["crash_datetime"] == datetime(2025, 11, 1)
    assert new["injured"] == 2 and new["killed"] == 1 and new["severity"] == "Killed" and new["road"] is None
    assert new["latitude"] == 40.5001


def test_bad_values():
    assert allegheny.parse(old_row(CRASH_MONTH=None))["crash_datetime"] is None
    assert allegheny.parse(old_row(DEC_LAT=None, DEC_LONG=None))["latitude"] is None
    assert allegheny.parse(new_row(DEC_LATITUDE=39.95, DEC_LONGITUDE=-75.16))["latitude"] is None  # Philadelphia
    assert allegheny.parse(new_row(MAX_SEVERITY_LEVEL=None))["severity"] is None


def test_fetch_pages_every_resource_by_row_id(tmp_path):
    spec = base.SourceSpec(**{**allegheny.SPEC.__dict__, "urls": allegheny.SPEC.urls[-2:], "page_size": 2})
    calls = []
    def get(url):
        sql = parse_qs(urlparse(url).query)["sql"][0]
        calls.append(sql)
        pages = [[old_row("1", _id=1), old_row("2", _id=2)], [old_row("3", _id=3)], [new_row(4)]]
        return {"success": True, "result": {"records": pages[len(calls) - 1]}}
    path = base.fetch(spec, None, raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(spec, base.iter_raw(path))
    assert sorted(r["source_id"] for r in parsed) == ["1", "2", "3", "4"] and skipped == 0
    assert '("_id" > 2)' in calls[1] and "CRASH_YEAR" not in calls[0]
