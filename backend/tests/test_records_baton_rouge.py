from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import baton_rouge as br


def br_row(rid="26-100001", when="2026-11-10T01:00:00.000", **extra):
    row = {"incident_number": rid, "crash_date": when, "street_name": "1200 MAIN ST", "city": "Baton Rouge",
           "weather": "Clear", "lighting": "Daylight", "has_injury": "1.0", "has_fatality": "0.0",
           "is_hit_and_run": "0.0", "manner_of_collision": "Rear end", "primary_factor": "Violations",
           "latitude": "30.4512345", "longitude": "-91.1523456"}
    row.update(extra)
    return row


def test_registered():
    assert records.all_specs()["baton_rouge"] is br.SPEC


def test_parse_fields_and_date_only():
    record = br.parse(br_row())
    assert record["source_id"] == "26-100001"
    assert record["crash_datetime"] == datetime(2026, 11, 10)  # placeholder 01:00 dropped
    assert (record["latitude"], record["longitude"]) == (30.4512345, -91.1523456)
    assert record["road"] == "1200 MAIN ST" and record["crash_type"] == "Rear end"
    assert record["primary_cause"] == "Violations" and record["hit_and_run"] is False
    assert record["injured"] is None and record["killed"] is None
    assert br.parse(br_row(when="1900-01-01T01:00:00"))["crash_datetime"] is None


def test_severity_from_flags():
    assert br.parse(br_row())["severity"] == "Injury"
    assert br.parse(br_row(has_injury="0.0", has_fatality="1.0"))["severity"] == "Fatal"
    assert br.parse(br_row(has_injury="0.0"))["severity"] == "No injury"
    assert br.parse(br_row(has_injury=None, has_fatality=None))["severity"] is None
    assert br.parse(br_row(is_hit_and_run="1.0"))["hit_and_run"] is True


def test_coordinates_outside_area_dropped():
    assert br.parse(br_row(latitude="0", longitude="0"))["latitude"] is None
    assert br.parse(br_row(latitude=None))["longitude"] is None


def test_repeated_incident_kept_once():
    records_, skipped = base.parse_all(br.SPEC, [br_row(), br_row(), br_row(incident_number=None)])
    assert len(records_) == 1 and skipped == 1
