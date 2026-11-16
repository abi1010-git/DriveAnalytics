from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import nc_serious


def row(cid=108000001, date="04/05/2025.", time="13:52", **extra):
    raw = {"FID": 1, "Crash_ID": cid, "Date": date, "Time": time, "Crash_Seve": "A", "Crash_Type": "Rear End, Slow Or Stop",
           "Weather": "Clear", "Light_Cond": "Daylight", "On_Road": "US 70", "County_Nam": "Orange", "City": "Rural",
           "Latitude": 36.0929511235, "Longitude": -79.2514728113, "_lat": 36.09295, "_lon": -79.25147}
    raw.update(extra)
    return raw


def test_registered_and_labelled_as_subset():
    spec = records.all_specs()["nc_serious"]
    assert spec is nc_serious.SPEC and spec.states == [37]
    assert "fatal & serious-injury crashes only" in spec.label


def test_parse_fields():
    r = nc_serious.parse(row())
    assert r["source_id"] == "108000001" and r["crash_datetime"] == datetime(2025, 4, 5, 13, 52)
    assert (r["latitude"], r["longitude"]) == (36.0929511235, -79.2514728113)
    assert r["severity"] == "Serious injury (A)" and r["injured"] is None and r["killed"] is None
    assert r["crash_type"] == "Rear End, Slow Or Stop" and r["road"] == "US 70"
    assert r["weather"] == "Clear" and r["lighting"] == "Daylight"


def test_text_dates():
    assert nc_serious.parse(row(date="10/10/2025.", time="7:19"))["crash_datetime"] == datetime(2025, 10, 10, 7, 19)
    assert nc_serious.parse(row(date="1/2/2016", time=None))["crash_datetime"] == datetime(2016, 1, 2)
    assert nc_serious.parse(row(time="25:61"))["crash_datetime"] == datetime(2025, 4, 5)
    assert nc_serious.parse(row(date="02/30/2025."))["crash_datetime"] is None
    assert nc_serious.parse(row(date=" "))["crash_datetime"] is None


def test_fatal_and_missing_coordinates():
    r = nc_serious.parse(row(Crash_Seve="K", Latitude=None, Longitude=None, _lat=None, _lon=None))
    assert r["severity"] == "Fatal (K)" and r["latitude"] is None
    parsed, skipped = base.parse_all(nc_serious.SPEC, [row(), row(cid=2, date="")])
    assert len(parsed) == 1 and skipped == 1
