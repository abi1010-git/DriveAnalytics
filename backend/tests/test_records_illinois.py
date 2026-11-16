from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import illinois


def row(crash_id=13000001, **extra):
    # 2025 layout (CrashExtract2025): DateOnly CrashDate, HHMMSS time, text coordinates, 0/1 hit-and-run
    raw = {"OBJECTID": 1, "CrashID": crash_id, "CrashYr": 25, "CrashMonth": 12, "CrashDay": 3, "CrashHour": 16,
           "CrashDate": "2025-12-03", "TimeOfCrash": "164500", "CrashSeverity": "Injury", "TotalFatals": 0,
           "TotalInjured": 3, "AInjuries": 1, "BInjuries": 0, "CInjuries": 2, "HitAndRun": 1,
           "HighwayorStreetName": "N Main St", "Cause1": "Following Too Closely", "WeatherCond": "Rain",
           "LightingCond": "Darkness / Lighted Road", "TypeOfFirstCrash": "Rear End",
           "TSCrashLatitude": "41.8800123456", "TSCrashLongitude": "-87.6300123456", "_lat": 41.88, "_lon": -87.63}
    raw.update(extra)
    return raw


def old_row(**extra):
    # 2021-2024 layout: epoch CrashDate, "hh:mm AM" time, numeric coordinates, Y/N, no street name
    raw = row(CrashID="11200002", CrashYr="22", CrashMonth=6, CrashDay=11, CrashHour="7", CrashDate=1654923600000,
              TimeOfCrash="07:06 PM", TSCrashLatitude=39.7, TSCrashLongitude=-89.6, HitAndRun="N")
    raw.pop("HighwayorStreetName")
    raw.update(extra)
    return raw


def test_registered():
    assert records.all_specs()["illinois"] is illinois.SPEC
    assert len(illinois.SPEC.urls) == 5 and illinois.SPEC.urls[-1].endswith("CrashExtract2025/FeatureServer/0")


def test_parse_2025_layout():
    r = illinois.parse(row())
    assert r["source_id"] == "13000001" and r["crash_datetime"] == datetime(2025, 12, 3, 16, 45)
    assert (r["latitude"], r["longitude"]) == (41.8800123456, -87.6300123456)
    assert r["injured"] == 3 and r["killed"] == 0 and r["severity"] == "Injury" and r["hit_and_run"] is True
    assert r["road"] == "N Main St" and r["primary_cause"] == "Following Too Closely"
    assert r["weather"] == "Rain" and r["lighting"] == "Darkness / Lighted Road" and r["crash_type"] == "Rear End"


def test_parse_older_layout():
    r = illinois.parse(old_row())
    assert r["source_id"] == "11200002" and r["crash_datetime"] == datetime(2022, 6, 11, 19, 6)
    assert r["road"] is None and r["hit_and_run"] is False and r["latitude"] == 39.7
    assert illinois.parse(old_row(TimeOfCrash="12:15 AM"))["crash_datetime"] == datetime(2022, 6, 11, 0, 15)


def test_time_fallback_and_missing_values():
    assert illinois.parse(row(TimeOfCrash="0000000000", CrashHour=0))["crash_datetime"] == datetime(2025, 12, 3, 0, 0)
    assert illinois.parse(row(CrashDay=None))["crash_datetime"] is None
    r = illinois.parse(row(HighwayorStreetName="(N/A)", Cause1="(UNK)", HitAndRun=None))
    assert r["road"] is None and r["primary_cause"] is None and r["hit_and_run"] is None


def test_coordinates_fall_back_and_bad_points_dropped():
    r = illinois.parse(row(TSCrashLatitude=None, TSCrashLongitude=None))
    assert (r["latitude"], r["longitude"]) == (41.88, -87.63)
    r = illinois.parse(row(TSCrashLatitude=None, TSCrashLongitude=None, _lat=36.41, _lon=-97.96))  # projected (0, 0)
    assert r["latitude"] is None and r["longitude"] is None


def test_duplicate_rows_collapse():
    parsed, skipped = base.parse_all(illinois.SPEC, [row(), row(OBJECTID=2), row(crash_id=13000002), row(CrashMonth=None)])
    assert sorted(r["source_id"] for r in parsed) == ["13000001", "13000002"] and skipped == 1
