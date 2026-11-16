from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import greenville_sc


def row(number=25000001, day=1767157200000, clock="1:30 PM", **extra):
    # 1767157200000 = 2025-12-31 05:00 UTC = local midnight (EST); the time is in Time_
    raw = {"FID": 1, "Crash_Number": number, "Crash_Date": day, "Time_": clock, "Time_of_Crash": 1785519000000,
           "County": "GREENVILLE", "SMS_Main_Street_Name": "WADE HAMPTON BLVD", "Light_Condition": "Daylight",
           "Road_Surface_Condition": "Dry", "Manner_of_Collision": "Angle 2", "F__of_Fatalities": 0,
           "F__of_Injuries": 2, "Probable_Cause": "Failure to Yield RoW", "Max_Injury_Code": "Possible Injury",
           "Latitude": 34.90929, "Longitude": -82.32693, "_lat": 34.909290313, "_lon": -82.326927185}
    raw.update(extra)
    return raw


def test_registered_with_2021_window():
    spec = records.all_specs()["greenville_sc"]
    assert spec is greenville_sc.SPEC and "2021-01-01" in spec.where and "2021-2025" in spec.label


def test_parse_fields():
    r = greenville_sc.parse(row())
    assert r["source_id"] == "25000001"
    assert r["crash_datetime"] == datetime(2025, 12, 31, 13, 30)
    assert (r["latitude"], r["longitude"]) == (34.90929, -82.32693)
    assert r["injured"] == 2 and r["killed"] == 0 and r["severity"] == "Possible Injury"
    assert r["primary_cause"] == "Failure to Yield RoW" and r["crash_type"] == "Angle 2"
    assert r["lighting"] == "Daylight" and r["road"] == "WADE HAMPTON BLVD" and r["weather"] is None


def test_summer_dates_and_odd_times():
    # 1751601600000 = 2025-07-04 04:00 UTC = local midnight (EDT)
    assert greenville_sc.parse(row(day=1751601600000, clock="12:05 AM"))["crash_datetime"] == datetime(2025, 7, 4, 0, 5)
    assert greenville_sc.parse(row(day=1751601600000, clock="12:45 PM"))["crash_datetime"] == datetime(2025, 7, 4, 12, 45)
    assert greenville_sc.parse(row(clock="25:99"))["crash_datetime"] == datetime(2025, 12, 31)
    assert greenville_sc.parse(row(clock=None))["crash_datetime"] == datetime(2025, 12, 31)
    assert greenville_sc.parse(row(day=None))["crash_datetime"] is None


def test_where_is_combined_with_since(tmp_path):
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return {"features": [{"attributes": row()}]}
    base.fetch(greenville_sc.SPEC, datetime(2025, 12, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    where = calls[0]["where"][0]
    assert "TIMESTAMP '2021-01-01 00:00:00'" in where and "TIMESTAMP '2025-12-01 00:00:00'" in where
