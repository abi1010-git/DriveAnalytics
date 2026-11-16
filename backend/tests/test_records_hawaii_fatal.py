from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import hawaii_fatal as hi


def row(gid="00000000-aaaa-bbbb-cccc-000000000001", when="2026-11-03T08:00:00.000Z", **extra):
    raw = {"the_geom": {"type": "Point", "coordinates": [-157.85, 21.31]}, "objectid": "1", "globalid": gid,
           "county": "Honolulu", "casenumber": "999999", "crash_date": when, "peds": "1", "remarks": "pending",
           "vehicle_type": "Pedestrian", "fatalsum": "1", "crashid": "26-000001"}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["hawaii_fatal"]
    assert spec is hi.SPEC and spec.label == "Hawaii fatal crashes" and "2019-01-01" in spec.where


def test_parse_fields():
    r = hi.parse(row())
    assert r["source_id"] == "00000000-aaaa-bbbb-cccc-000000000001"
    assert (r["latitude"], r["longitude"]) == (21.31, -157.85)
    assert r["killed"] == 1 and r["injured"] is None and r["crash_type"] == "Pedestrian"
    assert r["primary_cause"] is None and r["severity"] is None


def test_dates_are_hawaii_calendar_days():
    assert hi.parse(row())["crash_datetime"] == datetime(2026, 11, 2)  # 08:00Z = 22:00 HST the day before
    assert hi.parse(row(when="2023-08-02T22:00:00.000Z"))["crash_datetime"] == datetime(2023, 8, 2)
    assert hi.parse(row(when="2015-12-31T00:00:00.000Z"))["crash_datetime"] is None  # placeholder era
    assert hi.parse(row(when=None))["crash_datetime"] is None
    assert hi.parse(row(the_geom=None))["latitude"] is None


def test_id_is_stable_when_crashid_arrives(tmp_path):
    pages = [[row(crashid=None), row("g2")], [row(crashid="26-000009")]]
    seen = []
    def get(url):
        seen.append(parse_qs(urlparse(url).query))
        return pages[len(seen) - 1]
    spec = base.SourceSpec(**{**hi.SPEC.__dict__, "page_size": 2})
    parsed, skipped = base.parse_all(spec, base.iter_raw(base.fetch(spec, datetime(2026, 10, 1), raw_dir=tmp_path,
                                                                    get=get, log=lambda *_: None)))
    assert sorted(r["source_id"] for r in parsed) == ["00000000-aaaa-bbbb-cccc-000000000001", "g2"] and skipped == 0
    assert "crash_date >= '2019-01-01T00:00:00'" in seen[0]["$where"][0]
