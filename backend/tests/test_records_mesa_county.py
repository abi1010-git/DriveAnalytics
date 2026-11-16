from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import mesa_county as mc


def row(cuid=2600001, day="2025-12-31", clock="3:25:00 PM", **extra):
    raw = {"OBJECTID": 1, "CUID": cuid, "Crash_Date": day, "Crash_Time": clock, "Location_1": "G RD",
           "Location_2": "GALAXY DR", "Latitude": 39.1, "Longitude": -108.55, "Severity": "Minor Injury",
           "No_Apparent_Injury": 3, "Possible_Injury": 1, "Suspected_Minor_Injury": 1, "Suspected_Serious_Injury": 0,
           "Fatal_Injury": 0, "TotalInjured": 2, "TotalVehicles": 2, "TU_1_Hit_And_Run": 0, "TU_2_Hit_And_Run": 0,
           "Crash_Type": "Rear End", "Lighting_Conditions": "Daylight", "Weather_Condition_1": "Clear",
           "TU_1_Age": 30, "TU_1_Sex": "M", "Narrative": "TU1 ...", "_lat": 39.106, "_lon": -108.558}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["mesa_county"]
    assert spec is mc.SPEC and "Mesa County, CO" in spec.label and spec.refresh_days == 30


def test_parse_fields():
    r = mc.parse(row())
    assert r["source_id"] == "2025-2600001" and r["crash_datetime"] == datetime(2025, 12, 31, 15, 25)
    assert r["injured"] == 2 and r["killed"] == 0 and r["severity"] == "Minor Injury"
    assert r["road"] == "G RD & GALAXY DR" and r["crash_type"] == "Rear End" and r["hit_and_run"] is False
    assert (r["latitude"], r["longitude"]) == (39.106, -108.558) and r["weather"] == "Clear"
    assert "TU1 ..." not in r.values()


def test_times_ids_and_hit_and_run():
    assert mc.parse(row(clock="9:46 AM"))["crash_datetime"] == datetime(2025, 12, 31, 9, 46)
    assert mc.parse(row(clock="12:02:00 AM"))["crash_datetime"] == datetime(2025, 12, 31, 0, 2)
    assert mc.parse(row(clock=None))["crash_datetime"] == datetime(2025, 12, 31)
    assert mc.parse(row(day="2019-06-07"))["source_id"] == "2019-2600001"  # CUIDs repeat across years
    assert mc.parse(row(cuid=None))["source_id"] is None
    assert mc.parse(row(TU_2_Hit_And_Run=1))["hit_and_run"] is True
    assert mc.parse(row(TU_2_Hit_And_Run=None))["hit_and_run"] is None
    assert mc.parse(row(TotalVehicles=3))["hit_and_run"] is None
    assert mc.parse(row(TotalVehicles=1, TU_2_Hit_And_Run=None))["hit_and_run"] is False


def test_fetch(tmp_path):
    seen = []
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 2}
        seen.append(query)
        return {"features": [{"attributes": row(5)}, {"attributes": row(5, day="2019-01-02")}]}
    path = base.fetch(mc.SPEC, datetime(2018, 1, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(mc.SPEC, base.iter_raw(path))
    assert sorted(r["source_id"] for r in parsed) == ["2019-5", "2025-5"] and skipped == 0
    assert seen[0]["where"] == ["(Crash_Date >= TIMESTAMP '2018-01-01 00:00:00')"]
