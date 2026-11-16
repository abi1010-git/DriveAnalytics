from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import montana as mt


def row(day="2025-12-31", x=999621.62318, y=398016.8736, **extra):
    raw = {"OBJECTID": 7, "ROUTE_ID": "C000001A", "RP": "010+0.500", "CITY_NAME": "Sidney", "COUNTY": "Richland",
           "CRASH_DATE": day, "COL_TYPE": "Right Angle", "CRASH_SEVERITY": "Suspected Minor Injury", "WEATHER": "Clear",
           "SURF_COND": "Dry", "LIGHT_COND": "Daylight", "X_COORD": x, "Y_COORD": y, "_lat": 47.709, "_lon": -104.168}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["montana"]
    assert spec is mt.SPEC and spec.refresh_days == 30 and "2021-01-01" in spec.where


def test_parse_fields():
    r = mt.parse(row())
    assert r["crash_datetime"] == datetime(2025, 12, 31) and (r["latitude"], r["longitude"]) == (47.709, -104.168)
    assert r["severity"] == "Suspected Minor Injury" and r["crash_type"] == "Right Angle"
    assert r["weather"] == "Clear" and r["lighting"] == "Daylight"
    assert r["injured"] is None and r["killed"] is None and r["road"] is None
    assert r["source_id"].startswith("2025-12-31-") and len(r["source_id"]) == 27


def test_built_id_is_stable_and_specific():
    base_id = mt.parse(row())["source_id"]
    assert mt.parse(row(OBJECTID=99, CRASH_SEVERITY="Fatal crash", WEATHER="Snow"))["source_id"] == base_id
    assert mt.parse(row(x=999621.6249))["source_id"] == base_id  # rounded to 1 cm
    assert mt.parse(row(x=999622.0))["source_id"] != base_id
    assert mt.parse(row(day="2025-12-30"))["source_id"] != base_id
    assert mt.parse(row(COL_TYPE="Head On"))["source_id"] != base_id
    assert mt.parse(row(X_COORD=None))["source_id"] is None
    assert mt.parse(row(day=None))["crash_datetime"] is None


def test_fetch_collapses_identical_rows(tmp_path):
    seen = []
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 3}
        seen.append(query)
        return {"features": [{"attributes": row()}, {"attributes": row(OBJECTID=8)}, {"attributes": row(day="2025-12-01")}]}
    path = base.fetch(mt.SPEC, datetime(2025, 12, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(mt.SPEC, base.iter_raw(path))
    assert len(parsed) == 2 and skipped == 0
    assert seen[0]["where"] == ["(CRASH_DATE >= DATE '2021-01-01') AND (CRASH_DATE >= TIMESTAMP '2025-12-01 00:00:00')"]
