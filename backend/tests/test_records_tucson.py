from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import tucson


def tpd_row(number="2611130124", day="2026-11-13", hour="13:00:00", **extra):
    row = {"AccidentNumber": number, "Agency": "TPD", "Division": "West", "CollisionIntersection": "CONGRESS ST & CHURCH AVE",
           "OccurredDate": day, "OccurredYear": 2026, "OccurredHour": hour, "CollisionType": "Vehicle / Vehicle",
           "CollisionManner": "Rear End (Front to Back)", "FatalCollision": "No",
           "InjurySeverity": "Non-Incapacitating Injury", "TotalFatalities": "0", "TotalInjuries": "1",
           "HitAndRun": "No", "Latitude": 32.2217621, "Longitude": -110.972343, "OBJECTID": 4124,
           "_lon": -110.972343, "_lat": 32.2217621}
    row.update(extra)
    return row


def test_registered_with_one_service_per_year():
    spec = records.all_specs()["tucson"]
    assert spec is tucson.SPEC and len(spec.urls) == 9
    assert spec.urls[0].endswith("TPDOpenData_TrafficCollisions_2018/FeatureServer/0")
    assert spec.urls[-1].endswith("TPDOpenData_TrafficCollisions_2026/FeatureServer/0")


def test_parse():
    record = tucson.parse(tpd_row())
    assert record["source_id"] == "2611130124" and record["crash_datetime"] == datetime(2026, 11, 13, 13, 0)
    assert record["severity"] == "Non-Incapacitating Injury" and record["injured"] == 1 and record["killed"] == 0
    assert record["crash_type"] == "Rear End (Front to Back)" and record["road"] == "CONGRESS ST & CHURCH AVE"
    assert record["hit_and_run"] is False and tucson.parse(tpd_row(HitAndRun="Yes"))["hit_and_run"] is True
    fatal = tucson.parse(tpd_row(InjurySeverity="Fatal Injury", TotalFatalities="2", TotalInjuries=None))
    assert fatal["killed"] == 2 and fatal["injured"] is None and fatal["severity"] == "Fatal Injury"


def test_date_and_hour():
    assert tucson.parse(tpd_row(hour="00:00:00"))["crash_datetime"] == datetime(2026, 11, 13, 0, 0)
    assert tucson.parse(tpd_row(hour=None))["crash_datetime"] == datetime(2026, 11, 13)
    assert tucson.parse(tpd_row(hour="23:00:00", day="2018-01-01"))["crash_datetime"] == datetime(2018, 1, 1, 23)
    _, skipped = base.parse_all(tucson.SPEC, [tpd_row(day=None), tpd_row(day="garbage"), tpd_row("X")])
    assert skipped == 2


def test_coordinates():
    assert tucson.parse(tpd_row(Latitude=None, Longitude=None, _lat=None, _lon=None))["latitude"] is None
    assert tucson.parse(tpd_row(Latitude=0, Longitude=0))["latitude"] == 32.2217621  # geometry fallback
    assert tucson.parse(tpd_row(Latitude=33.45, Longitude=-112.07, _lat=None, _lon=None))["latitude"] is None  # Phoenix
