from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import dallas_county


def row(cid=20500001, day="2025-01-03", tm=1540, **extra):
    raw = {"ObjectId": 1, "Crash_ID": cid, "Case_ID": "25-000001", "Crash_Date": day, "Crash_Time": tm,
           "Crash_Severity": "C - POSSIBLE INJURY", "Crash_Total_Injury_Count": 1, "Fatal_Crash_Flag": 0,
           "Street_Name": "MAIN ST", "Street_Number": "1300", "Weather_Condition": "1 - CLEAR",
           "Vehicle_Hit_and_Run_Flag": "No", "Latitude": 32.7801, "Longitude": -96.8001,
           "Person_Age": "44", "Person_Gender": "1 - MALE", "Person_Ethnicity": "1 - WHITE",
           "Person_Alcohol_Result": "No Data", "Person_Death_Count": 0, "Person_Type": "1 - DRIVER",
           "_lat": 32.78, "_lon": -96.8}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["dallas_county"]
    assert spec is dallas_county.SPEC and spec.tz == "America/Chicago" and "2025 only" in spec.label


def test_parse_fields():
    r = dallas_county.parse(row())
    assert r["source_id"] == "20500001" and r["crash_datetime"] == datetime(2025, 1, 3, 15, 40)
    assert (r["latitude"], r["longitude"]) == (32.7801, -96.8001)
    assert r["injured"] == 1 and r["killed"] == 0 and r["severity"] == "C - POSSIBLE INJURY"
    assert r["road"] == "1300 MAIN ST" and r["weather"] == "CLEAR" and r["hit_and_run"] is None
    assert "MALE" not in str(r) and "44" not in str(r)  # person columns never stored


def test_fatal_unknown_and_text_dates():
    r = dallas_county.parse(row(Fatal_Crash_Flag=1, Crash_Severity="K - FATAL INJURY", Vehicle_Hit_and_Run_Flag="Yes",
                                Street_Number="NO DATA", Weather_Condition="99 - UNKNOWN"))
    assert r["killed"] is None and r["hit_and_run"] is True and r["road"] == "MAIN ST" and r["weather"] is None
    assert dallas_county.parse(row(day="12/31/2025", tm=5))["crash_datetime"] == datetime(2025, 12, 31, 0, 5)
    assert dallas_county.parse(row(tm=2575))["crash_datetime"] == datetime(2025, 1, 3)
    assert dallas_county.parse(row(day="not a date"))["crash_datetime"] is None
    assert dallas_county.parse(row(Latitude=None, Longitude=None, _lat=None, _lon=None))["latitude"] is None


def test_duplicate_crash_ids_keep_more_severe():
    rows = [row(Crash_Severity="N - NOT INJURED", Crash_Total_Injury_Count=0), row(), row(cid=20500002)]
    parsed, skipped = base.parse_all(dallas_county.SPEC, rows)
    by_id = {r["source_id"]: r for r in parsed}
    assert len(parsed) == 2 and skipped == 0 and by_id["20500001"]["injured"] == 1
    assert dallas_county.reduce([dallas_county.parse(row(Fatal_Crash_Flag=1, Crash_Total_Injury_Count=0)),
                                 dallas_county.parse(row(Crash_Total_Injury_Count=4))])["killed"] is None
