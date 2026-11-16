from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import gainesville


def row(dhsmv="28000001", case="226000001", **extra):
    raw = {"case_number": case, "dhsmv_number": dhsmv, "accident_date": "2026-09-09T20:58:18.000",
           "accident_hour_of_day": "20", "crash_minutes": "58", "occurred_on": "SR 24 (SW ARCHER RD)",
           "intersecttype": "NOT AT INTERSECTION", "totalvehiclesinvolved": "2", "totalfatalities": "0",
           "latitude": "29.65198", "longitude": "-82.32265",
           "location": {"type": "Point", "coordinates": [-82.3, 29.7]}, "city": "Gainesville", "state": "Florida"}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["gainesville"]
    assert spec is gainesville.SPEC and spec.states == [12] and "60" in spec.label


def test_parse_fields():
    r = gainesville.parse(row())
    assert r["source_id"] == "28000001"
    assert r["crash_datetime"] == datetime(2026, 9, 9, 20, 58, 18)
    assert (r["latitude"], r["longitude"]) == (29.65198, -82.32265)  # not the `location` point
    assert r["killed"] == 0 and r["injured"] is None and r["severity"] is None
    assert r["road"] == "SR 24 (SW ARCHER RD)"


def test_repeated_case_numbers_stay_separate():
    parsed, _ = base.parse_all(gainesville.SPEC, [row("1", case="0"), row("2", case="0")])
    assert len(parsed) == 2


def test_bad_values():
    r = gainesville.parse(row(latitude="36.60335", longitude="-97.30043", totalfatalities="2"))
    assert r["latitude"] is None and r["killed"] == 2
    r = gainesville.parse(row(latitude=None, longitude=None, accident_date="1900-01-01T00:00:00.000"))
    assert r["latitude"] is None and r["crash_datetime"] is None


def test_socrata_since_filter(tmp_path):
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return [row()]
    base.fetch(gainesville.SPEC, datetime(2026, 8, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    assert "accident_date >= '2026-08-01T00:00:00'" in calls[0]["$where"][0]
