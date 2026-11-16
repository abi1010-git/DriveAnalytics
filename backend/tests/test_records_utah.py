from datetime import datetime
from urllib.parse import urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import utah


def row(cid=8261068116, when="2026-11-11T21:09:33+00:00", **extra):
    raw = {"OBJECTID": 1, "crash_id": cid, "crash_datetime": when, "main_road_name": "S BANDED HILLS DR",
           "crash_severity_desc": "Suspected Minor Injury", "light_condition_desc": "Dark - Lighted",
           "weather_condition_desc": "Clear", "manner_collision_desc": "Angle", "hit_and_run": "N",
           "number_fatalities": 0, "number_four_injuries": 1, "number_three_injuries": 2, "number_two_injuries": 1,
           "number_one_injuries": 3, "_lon": -113.58, "_lat": 37.08}
    raw.update(extra)
    return raw


def test_registered_with_all_year_layers():
    spec = records.all_specs()["utah"]
    assert spec is utah.SPEC and len(spec.urls) == 8 and spec.urls[-1].endswith("/7")


def test_parse_fields():
    r = utah.parse(row())
    assert r["source_id"] == "8261068116"
    assert (r["latitude"], r["longitude"]) == (37.08, -113.58)
    assert r["injured"] == 4 and r["killed"] == 0  # number_one_injuries are uninjured people
    assert r["severity"] == "Suspected Minor Injury" and r["crash_type"] == "Angle"
    assert r["weather"] == "Clear" and r["lighting"] == "Dark - Lighted" and r["hit_and_run"] is False
    assert r["road"] == "S BANDED HILLS DR" and r["primary_cause"] is None
    assert utah.parse(row(hit_and_run="Y"))["hit_and_run"] is True


def test_timestamp_offset_strings_are_utc():
    assert utah.parse(row())["crash_datetime"] == datetime(2026, 11, 11, 14, 9, 33)  # MST, UTC-7
    assert utah.parse(row(when="2025-07-04T18:30:00+00:00"))["crash_datetime"] == datetime(2025, 7, 4, 12, 30)  # MDT
    assert utah.parse(row(when=1794503460000))["crash_datetime"] == datetime(2026, 11, 12, 10, 11)  # epoch fallback
    assert utah.parse(row(when="garbage"))["crash_datetime"] is None
    assert utah.parse(row(when=None))["crash_datetime"] is None


def test_pdo_and_bad_coordinates():
    r = utah.parse(row(crash_severity_desc="No Injury/PDO", number_four_injuries=0, number_three_injuries=0,
                       number_two_injuries=0, _lat=40.7, _lon=-74.0))
    assert r["injured"] == 0 and r["latitude"] is None


def test_reads_every_layer_and_dedupes(tmp_path):
    spec = base.SourceSpec(**{**utah.SPEC.__dict__, "urls": utah.SPEC.urls[:2]})
    seen = []
    def get(url):
        seen.append(urlparse(url).path)
        cid = 1 if len(seen) == 1 else 2
        return {"features": [{"attributes": row(cid), "geometry": {"x": -111.9, "y": 40.7}},
                             {"attributes": row(1, OBJECTID=2), "geometry": {"x": -111.9, "y": 40.7}}]}
    path = base.fetch(spec, datetime(2026, 11, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(spec, base.iter_raw(path))
    assert [p.split("/")[-2] for p in seen] == ["0", "1"]
    assert sorted(r["source_id"] for r in parsed) == ["1", "2"] and skipped == 0
    assert parsed[0]["latitude"] == 40.7
