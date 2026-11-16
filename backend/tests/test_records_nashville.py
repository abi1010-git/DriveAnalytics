from datetime import datetime, timezone

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import nashville as nash


def ms(*args):
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def nash_row(number=20260680001.0, when=None, **extra):
    row = {"Accident_Number": number, "Date_and_Time": ms(2026, 11, 14, 2, 48) if when is None else when,
           "Number_of_Motor_Vehicles": 2.0, "Number_of_Injuries": 2.0, "Number_of_Fatalities": 0.0,
           "Property_Damage": None, "Hit_and_Run": "Y", "Collision_Type_Description": "SIDESWIPE - SAME DIRECTION",
           "Weather_Description": "NO ADVERSE CONDITIONS", "Illumination_Description": "DARK - LIGHTED",
           "Street_Address": "GALLATIN PIKE S & EMMITT AVE", "City": "MADISON", "Lat": 36.25302, "Long": -86.71681,
           "ObjectId": 2042, "_lon": -86.71681, "_lat": 36.25302}
    row.update(extra)
    return row


def test_registered():
    assert records.all_specs()["nashville"] is nash.SPEC


def test_parse():
    record = nash.parse(nash_row())
    assert record["source_id"] == "20260680001"  # Double id stored as integer text
    assert record["crash_datetime"] == datetime(2026, 11, 13, 20, 48)  # true UTC -> CST
    assert record["injured"] == 2 and record["killed"] == 0 and record["severity"] is None
    assert record["hit_and_run"] is True and nash.parse(nash_row(Hit_and_Run="N"))["hit_and_run"] is False
    assert nash.parse(nash_row(Hit_and_Run=None))["hit_and_run"] is None
    assert record["weather"] == "NO ADVERSE CONDITIONS" and record["lighting"] == "DARK - LIGHTED"
    assert record["crash_type"] == "SIDESWIPE - SAME DIRECTION" and record["road"] == "GALLATIN PIKE S & EMMITT AVE"


def test_dates():
    assert nash.parse(nash_row(when=ms(2019, 1, 1, 6)))["crash_datetime"] == datetime(2019, 1, 1)  # local midnight CST
    assert nash.parse(nash_row(when=ms(2025, 7, 4, 22, 15)))["crash_datetime"] == datetime(2025, 7, 4, 17, 15)  # CDT
    _, skipped = base.parse_all(nash.SPEC, [nash_row(when=None, Date_and_Time=None), nash_row(Accident_Number=None)])
    assert skipped == 2


def test_coordinates():
    assert nash.parse(nash_row(Lat=0, Long=0, _lat=None, _lon=None))["latitude"] is None
    assert nash.parse(nash_row(Lat=None, Long=None))["latitude"] == 36.25302  # geometry fallback
    assert nash.parse(nash_row(Lat=35.1, Long=-90.0, _lat=None, _lon=None))["longitude"] is None  # Memphis: outside bbox
