from datetime import datetime, timezone

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import dc


def ms(*args):
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def dc_row(crime_id="74800000001", when=None, **extra):
    row = {"CRIMEID": crime_id, "CCN": "26100001", "REPORTDATE": ms(2026, 11, 13, 21, 20) if when is None else when,
           "ADDRESS": "2700 MARTIN LUTHER KING JR AVENUE SE", "LATITUDE": 38.8549, "LONGITUDE": -76.9961,
           "MAJORINJURIES_DRIVER": 1, "MINORINJURIES_DRIVER": 0, "UNKNOWNINJURIES_DRIVER": 0, "FATAL_DRIVER": 0,
           "MAJORINJURIES_PEDESTRIAN": 0, "MINORINJURIES_PEDESTRIAN": 2, "UNKNOWNINJURIES_PEDESTRIAN": 0,
           "FATAL_PEDESTRIAN": 1, "MAJORINJURIES_BICYCLIST": 0, "MINORINJURIES_BICYCLIST": 0,
           "UNKNOWNINJURIES_BICYCLIST": 0, "FATAL_BICYCLIST": 0, "MAJORINJURIESPASSENGER": 0.0,
           "MINORINJURIESPASSENGER": 1.0, "UNKNOWNINJURIESPASSENGER": 0.0, "FATALPASSENGER": 0.0,
           "MAJORINJURIESOTHER": None, "MINORINJURIESOTHER": None, "UNKNOWNINJURIESOTHER": None, "FATALOTHER": None,
           "_lon": -76.99605, "_lat": 38.85497}
    row.update(extra)
    return row


def test_registered():
    assert records.all_specs()["dc"] is dc.SPEC


def test_parse_counts_and_time():
    record = dc.parse(dc_row())
    assert record["source_id"] == "74800000001"
    assert record["crash_datetime"] == datetime(2026, 11, 13, 16, 20)  # true UTC -> Eastern
    assert record["injured"] == 4 and record["killed"] == 1  # major+minor across driver, pedestrian, passenger
    assert record["severity"] is None and record["hit_and_run"] is None
    assert record["road"] == "2700 MARTIN LUTHER KING JR AVENUE SE"


def test_summer_time_and_date_only_rows():
    assert dc.parse(dc_row(when=ms(2016, 6, 1, 4, 54, 49)))["crash_datetime"] == datetime(2016, 6, 1, 0, 54, 49)
    assert dc.parse(dc_row(when=ms(2015, 1, 1, 5)))["crash_datetime"] == datetime(2015, 1, 1)


def test_junk_dates_are_skipped():
    assert dc.parse(dc_row(when=ms(1900, 1, 1, 5)))["crash_datetime"] is None
    assert dc.parse(dc_row(REPORTDATE=None))["crash_datetime"] is None
    _, skipped = base.parse_all(dc.SPEC, [dc_row(REPORTDATE=ms(1825, 11, 8, 11, 57)), dc_row("2")])
    assert skipped == 1


def test_coordinates_and_road_cleanup():
    record = dc.parse(dc_row(LATITUDE=0, LONGITUDE=0))
    assert (record["latitude"], record["longitude"]) == (38.85497, -76.99605)  # falls back to geometry
    assert dc.parse(dc_row(LATITUDE=0, LONGITUDE=0, _lat=None, _lon=None))["latitude"] is None
    assert dc.parse(dc_row(ADDRESS="INTERSTATE 295 INTERSTATE BN\nWASHINGTON,"))["road"] == "INTERSTATE 295 INTERSTATE BN"


def test_missing_count_columns_stay_unknown():
    row = {k: v for k, v in dc_row().items() if "INJURIES" not in k and "FATAL" not in k}
    record = dc.parse(row)
    assert record["injured"] is None and record["killed"] is None
