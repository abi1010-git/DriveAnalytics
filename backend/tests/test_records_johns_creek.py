from datetime import datetime

from pipeline.records import base
from pipeline.records.sources import johns_creek as jc


def jc_row(rid="2026000123", occured="2026-11-14T13:03:40.000", hhmm="1150", **extra):
    row = {"accidentid": rid, "case_id": rid, "occured": occured, "timeoccurred": hhmm, "street": "MEDLOCK BRIDGE RD",
           "intersection": "ABBOTTS BRIDGE RD", "geox": "34.0477867126465", "geoy": "-84.1900177001953",
           "location": {"latitude": "34.0477867126465", "longitude": "-84.1900177001953"},
           "rdconditiondesc": "REAR END", "lightconddesc": "DAYLIGHT", "weatherdesc": "CLEAR", "supprept": "False"}
    row.update(extra)
    return row


def test_parse_fields_and_coordinates():
    record = jc.parse(jc_row())
    assert record["source_id"] == "2026000123" and record["road"] == "MEDLOCK BRIDGE RD & ABBOTTS BRIDGE RD"
    assert record["latitude"] == 34.0477867126465 and record["longitude"] == -84.1900177001953  # geox = lat
    assert record["crash_type"] == "REAR END" and record["weather"] == "CLEAR" and record["lighting"] == "DAYLIGHT"
    assert record["severity"] is None and record["injured"] is None and record["hit_and_run"] is None
    assert jc.parse(jc_row(intersection=None))["road"] == "MEDLOCK BRIDGE RD"
    swapped = jc.parse(jc_row(geox="-84.19", geoy="34.04"))
    assert swapped["latitude"] is None and swapped["longitude"] is None
    assert jc.parse(jc_row(geox=None, geoy=None))["latitude"] is None


def test_crash_time_uses_timeoccurred():
    assert jc.parse(jc_row())["crash_datetime"] == datetime(2026, 11, 14, 11, 50)
    assert jc.parse(jc_row(occured="2023-06-27T00:00:00.000", hhmm="1235"))["crash_datetime"] == datetime(2023, 6, 27, 12, 35)
    assert jc.parse(jc_row(hhmm="99x"))["crash_datetime"] == datetime(2026, 11, 14, 13, 3, 40)
    assert jc.parse(jc_row(occured="1825-01-01T00:00:00.000"))["crash_datetime"] is None


def test_id_stable_and_supplement_dropped():
    assert jc.parse(jc_row())["source_id"] == jc.parse(jc_row(weatherdesc="RAIN"))["source_id"]
    original = jc_row(occured="2026-03-13T14:05:00.000", hhmm="1405")
    supplement = jc_row(occured="2026-03-13T15:49:47.000", hhmm="1405", supprept="True", geox=None, geoy=None)
    records, skipped = base.parse_all(jc.SPEC, [supplement, original])
    assert skipped == 0 and len(records) == 1 and records[0]["latitude"] == 34.0477867126465
