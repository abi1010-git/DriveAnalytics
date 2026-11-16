from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import oregon_fatal as orf


def row(no=20269001, day=1794038400000, tm=1020, **extra):
    raw = {"OBJECTID": 1, "ST_ACDT": no, "ACDT_DT": day, "ACDT_TM": tm, "ACDT_TM_DSPLY": "10:20", "1Y": "Malheur",
           "ROAD": "SUCCOR CREEK HWY", "ROAD_INT": "OVERSTREET RD", "LAT": 43.77, "LONGTD": -117.07, "CASE_NUM": "26-",
           "HIT_RUN": "No", "HARMFUL": "Angle", "NUM_FATALS": 2, "AGES": "40", "GENDERS": "Female", "REMOVED": 0,
           "_lat": 43.766, "_lon": -117.066}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["oregon_fatal"]
    assert spec is orf.SPEC and "preliminary" in spec.label and "REMOVED" in spec.where


def test_parse_fields_and_no_personal_data():
    r = orf.parse(row())
    assert r["source_id"] == "20269001" and r["crash_datetime"] == datetime(2026, 11, 7, 10, 20)  # 08:00 UTC = PST midnight
    assert r["killed"] == 2 and r["injured"] is None and r["severity"] is None
    assert r["road"] == "SUCCOR CREEK HWY & OVERSTREET RD" and r["crash_type"] == "Angle" and r["hit_and_run"] is False
    assert (r["latitude"], r["longitude"]) == (43.766, -117.066)
    assert "40" not in map(str, r.values()) and "Female" not in r.values()


def test_times_removed_and_fallbacks():
    assert orf.parse(row(day=1783062000000, tm=5))["crash_datetime"] == datetime(2026, 7, 3, 0, 5)  # 07:00 UTC = PDT midnight
    assert orf.parse(row(tm=None))["crash_datetime"] == datetime(2026, 11, 7, 0, 0)
    assert orf.parse(row(REMOVED=1)) is None
    assert orf.parse(row(HIT_RUN="Yes"))["hit_and_run"] is True and orf.parse(row(HIT_RUN="Unknown"))["hit_and_run"] is None
    assert orf.parse(row(_lat=None, _lon=None))["latitude"] == 43.77


def test_fetch(tmp_path):
    seen = []
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 1}
        seen.append(query)
        return {"features": [{"attributes": row(1), "geometry": {"x": -123.0, "y": 44.9}}]}
    path = base.fetch(orf.SPEC, datetime(2026, 10, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(orf.SPEC, base.iter_raw(path))
    assert [r["latitude"] for r in parsed] == [44.9] and skipped == 0
    assert "(REMOVED IS NULL OR REMOVED <> 1) AND (ACDT_DT >= TIMESTAMP '2026-10-01 00:00:00')" == seen[0]["where"][0]
