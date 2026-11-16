from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import connecticut as ct


def row(crash_id=1448576, when=1794605880000, **extra):
    # 1794605880000 = 2026-11-13 21:38 UTC = 16:38 EST (CrashTimeHour 16); the server returns true UTC
    raw = {"OBJECTID": 1, "CrashID": crash_id, "CrashDate": when, "CrashTimeHour": 16, "CrashDateYear": 2026,
           "NameOfRoadway": "15-N", "NameOfIntersectingRoadway": None,
           "CrashSeverity": "Injury of any type (Serious, Minor, Possible)", "MostSevereInjury": "Possible Injury (C)",
           "WeatherCondition": "Clear", "LightCondition": "Dark-Lighted", "MannerOfCrashCollisionImpact": "Front to rear",
           "_lon": -72.774738, "_lat": 41.518159}
    raw.update(extra)
    return raw


def test_registered_and_bounded():
    spec = records.all_specs()["connecticut"]
    assert spec is ct.SPEC and not spec.epoch_is_local and "2019-01-01" in spec.where
    assert "TERMS NOT CONFIRMED" in spec.notes


def test_parse_fields_and_utc_time():
    r = ct.parse(row())
    assert r["source_id"] == "1448576" and r["crash_datetime"] == datetime(2026, 11, 13, 16, 38)
    assert (r["latitude"], r["longitude"]) == (41.518159, -72.774738)
    assert r["severity"] == "Possible Injury (C)" and r["injured"] is None and r["killed"] is None
    assert r["road"] == "15-N" and r["crash_type"] == "Front to rear"
    assert r["weather"] == "Clear" and r["lighting"] == "Dark-Lighted" and r["hit_and_run"] is None


def test_summer_time_uses_daylight_offset():
    # 2025-07-01 16:05 UTC = 12:05 EDT
    assert ct.parse(row(when=1751385900000))["crash_datetime"] == datetime(2025, 7, 1, 12, 5)


def test_severity_fallback_and_unknown_labels():
    r = ct.parse(row(MostSevereInjury=None, CrashSeverity="Fatal (Kill)", MannerOfCrashCollisionImpact="Not Applicable",
                     WeatherCondition="Unknown", LightCondition="Other"))
    assert r["severity"] == "Fatal (Kill)" and r["crash_type"] is None
    assert r["weather"] is None and r["lighting"] is None


def test_coordinates_and_ids():
    r = ct.parse(row(_lat=None, _lon=None))
    assert r["latitude"] is None and r["longitude"] is None
    assert ct.parse(row(_lat=40.7, _lon=-74.0))["latitude"] is None  # New York City, outside CT
    parsed, skipped = base.parse_all(ct.SPEC, [row(), row(crash_id=None), row(when=None), row(crash_id=1448577)])
    assert sorted(r["source_id"] for r in parsed) == ["1448576", "1448577"] and skipped == 2
