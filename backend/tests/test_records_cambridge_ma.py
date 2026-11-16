from datetime import datetime

from pipeline.records import base
from pipeline.records.sources import cambridge_ma as cam


def cam_row(when="2026-10-31T17:28:00.000", **extra):
    row = {"date_time": when, "street_number": "699  ", "street_name": "MT AUBURN ST                    ",
           "cross_street": "", "location": {"latitude": "42.37496", "longitude": "-71.14916",
                                            "human_address": '{"address": "699 MT AUBURN ST", "city": "Cambridge"}'},
           "manner_of_collision": "ANGLE                ", "ambient_light": "DAYLIGHT          ",
           "weather_condition_1": "CLEAR      ", "p1_injury": "NO APPARENT INJURY      ", "p2_injury": "",
           "v1_hit_and_run": "", "v2_hit_and_run": ""}
    row.update(extra)
    return row


def test_parse_fields_and_coordinates():
    record = cam.parse(cam_row())
    assert record["crash_datetime"] == datetime(2026, 10, 31, 17, 28)
    assert record["latitude"] == 42.37496 and record["longitude"] == -71.14916
    assert record["road"] == "MT AUBURN ST" and record["crash_type"] == "ANGLE" and record["weather"] == "CLEAR"
    assert record["lighting"] == "DAYLIGHT" and record["hit_and_run"] is None and record["injured"] is None
    assert cam.parse(cam_row(cross_street="BROADWAY "))["road"] == "MT AUBURN ST & BROADWAY"
    assert cam.parse(cam_row(location=None))["latitude"] is None
    assert cam.parse(cam_row(location={"human_address": "{}"}))["latitude"] is None
    assert cam.parse(cam_row(location={"latitude": "0", "longitude": "0"}))["latitude"] is None
    assert cam.parse(cam_row(v2_hit_and_run="Y"))["hit_and_run"] is True


def test_severity_is_most_severe_person_label():
    assert cam.parse(cam_row())["severity"] == "NO APPARENT INJURY"
    assert cam.parse(cam_row(p2_injury="SUSPECTED SERIOUS INJURY  "))["severity"] == "SUSPECTED SERIOUS INJURY"
    assert cam.parse(cam_row(p1_injury="NON FATAL INJURY - POSSIBLE", p2_injury="FATAL INJURY"))["severity"] == "FATAL INJURY"
    assert cam.parse(cam_row(p1_injury="UNKNOWN", p2_injury="NOT APPLICABLE"))["severity"] is None


def test_built_id_is_stable():
    a = cam.parse(cam_row())["source_id"]
    assert a.startswith("2026-10-31T17:28-") and len(a) <= 160
    # padding, case and non-key fields (injury, location, weather) don't change the id
    same = cam.parse(cam_row(street_name="mt auburn st", street_number="699", p1_injury="POSSIBLE INJURY",
                             location=None, weather_condition_1="RAIN"))["source_id"]
    assert same == a
    assert cam.parse(cam_row(street_number="700"))["source_id"] != a
    assert cam.parse(cam_row(when="2026-10-31T17:29:00.000"))["source_id"] != a
    records, skipped = base.parse_all(cam.SPEC, [cam_row(), cam_row(p1_injury="FATAL INJURY"), cam_row(when=None)])
    assert len(records) == 1 and skipped == 1  # same key collapses (documented risk)
