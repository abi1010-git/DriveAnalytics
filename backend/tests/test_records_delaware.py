from datetime import datetime

from pipeline.records import base
from pipeline.records.sources import delaware as de


def de_row(when="2023-11-01T17:30:00.000Z", **extra):
    row = {"crash_datetime": when, "crash_class": "03", "crash_class_desc": "Personal Injury Crash",
           "impact_desc": "Angle", "light_cond_desc": "Daylight", "weather_1_desc": "Clear",
           "pri_contrib_circum_desc": "Disregard Traffic Signal", "latitude": "39.75106", "longitude": "-75.55478",
           "the_geom": {"type": "Point", "coordinates": [-75.55478000002, 39.751059999889]},
           "county_desc": "New Castle", "year": "2023"}
    row.update(extra)
    return row


def test_parse_fields_and_coordinates():
    record = de.parse(de_row())
    assert record["latitude"] == 39.75106 and record["longitude"] == -75.55478
    assert record["severity"] == "Personal Injury Crash" and record["crash_type"] == "Angle"
    assert record["primary_cause"] == "Disregard Traffic Signal" and record["weather"] == "Clear"
    assert record["lighting"] == "Daylight" and record["road"] is None and record["injured"] is None
    assert de.parse(de_row(latitude="8.7756"))["latitude"] is None  # bad point outside Delaware
    assert de.parse(de_row(latitude=None, longitude=None))["longitude"] is None


def test_severity_and_na():
    assert de.parse(de_row(crash_class_desc="Fatality Crash"))["severity"] == "Fatality Crash"
    assert de.parse(de_row(crash_class_desc="NA", weather_1_desc="NA"))["severity"] is None
    assert de.parse(de_row(weather_1_desc="NA"))["weather"] is None


def test_utc_converted_to_local():
    assert de.parse(de_row())["crash_datetime"] == datetime(2023, 11, 1, 13, 30)  # EDT
    assert de.parse(de_row(when="2020-01-01T00:37:00.000Z"))["crash_datetime"] == datetime(2019, 12, 31, 19, 37)  # EST
    assert de.parse(de_row(when="2022-05-26T04:00:00.000Z"))["crash_datetime"] == datetime(2022, 5, 26, 0, 0)
    assert de.parse(de_row(when=None))["crash_datetime"] is None


def test_built_id_is_stable():
    a = de.parse(de_row())["source_id"]
    assert a == "2023-11-01T17:30:00|39.75106|-75.55478"
    assert de.parse(de_row(crash_class_desc="Fatality Crash", weather_1_desc="Rain"))["source_id"] == a
    assert de.parse(de_row(latitude="39.751060"))["source_id"] == a
    assert de.parse(de_row(latitude=None, longitude=None))["source_id"] == "2023-11-01T17:30:00||"
    records, skipped = base.parse_all(de.SPEC, [de_row(), de_row(longitude="-75.55479"), de_row(when=None)])
    assert len(records) == 2 and skipped == 1
