from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import knoxville


def row(when=1768514700000, **extra):
    # 1768514700000 = 2026-01-15 22:05 UTC = 17:05 EST
    raw = {"OBJECTID": 7, "GlobalID": "00000000-0000-0000-0000-000000000001", "Date_of_Crash": when,
           "Gps_Coordinate_Latitude": 35.96061, "Gps_Coordinate_Longitude": -83.92074, "_lat": 35.9606, "_lon": -83.9207,
           "Road_Name": "Kingston Pike", "Route": "0001", "Log_Mile": 12.345, "Total_Vehicles": 2,
           "Manner_of_First_Collision": "Rear-End", "First_Harmful_Event": "Vehicle in Transport",
           "Type_of_Crash": "(B) Suspected Minor Injury", "Total_Fatalities": 0, "Total_Injured": 3,
           "Total_Suspected_Serious_Injuries": 1, "Total_Other_Injuries": 1, "Light_Conditions": "Daylight",
           "Weather_Conditions": "Clear", "Person_Age": "[30, 40]", "Person_Type": "['Driver', 'Driver']",
           "Driver_Age": "[30, 40]"}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["knoxville"]
    assert spec is knoxville.SPEC and spec.states == [47] and spec.tz == "America/New_York"


def test_parse_fields():
    r = knoxville.parse(row())
    assert r["crash_datetime"] == datetime(2026, 1, 15, 17, 5)
    assert (r["latitude"], r["longitude"]) == (35.96061, -83.92074)
    assert r["injured"] == 2 and r["killed"] == 0  # Total_Injured (3) is not an injury count
    assert r["severity"] == "(B) Suspected Minor Injury" and r["crash_type"] == "Rear-End"
    assert r["road"] == "Kingston Pike" and r["weather"] == "Clear" and r["lighting"] == "Daylight"
    assert "30" not in str({k: v for k, v in r.items() if k != "source_id"})  # no person data carried over


def test_derived_id_is_stable_and_discriminating():
    first = knoxville.parse(row())["source_id"]
    assert first.startswith("202601151705_35.96061_-83.92074_")
    assert knoxville.parse(row(OBJECTID=99, GlobalID="other", Person_Age="[1]"))["source_id"] == first
    assert knoxville.parse(row(Total_Vehicles=3))["source_id"] != first
    assert knoxville.parse(row(when=1768514760000))["source_id"] != first
    assert knoxville.parse(row(when=None))["source_id"] is None


def test_date_only_and_blank_values():
    # 1790740800000 = 2026-09-30 04:00 UTC = local midnight (date only)
    r = knoxville.parse(row(when=1790740800000, Weather_Conditions=" ", Road_Name=None))
    assert r["crash_datetime"] == datetime(2026, 9, 30) and r["weather"] is None and r["road"] is None
    r = knoxville.parse(row(Gps_Coordinate_Latitude=0, Gps_Coordinate_Longitude=0))
    assert r["latitude"] == 35.9606  # falls back to geometry


def test_identical_rows_collapse():
    parsed, skipped = base.parse_all(knoxville.SPEC, [row(), row(OBJECTID=8), row(Total_Vehicles=1)])
    assert len(parsed) == 2 and skipped == 0
