from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import vermont as vt


def row(rid="26SB017534", when=1794579420000, **extra):
    # 1794579420000 = 2026-11-13 14:17 "as UTC"; Vermont stores local wall time this way
    raw = {"OBJECTID": 1, "REPORTNUMBER": rid, "REPORTINGAGENCYid": "VT0040300", "ACCIDENTDATE": when,
           "STREETADDRESS": "918-938 Shelburne Rd", "INTERSECTIONWITH": "Brewer Pkwy", "DirOfCollision": "Rear End",
           "InjuryType": "Property Damage Only", "Impairment": "None", "Involving": "Heavy Truck", "Weather": "Clear",
           "DayNight": "Day", "RDFLNAME": "SHELBURNE RD", "Route": "US-7", "LATITUDE": 44.4429553,
           "LONGITUDE": -73.20977389, "_lat": 44.44296, "_lon": -73.20978}
    raw.update(extra)
    return raw


def test_registered():
    assert records.all_specs()["vermont"] is vt.SPEC and vt.SPEC.epoch_is_local


def test_parse_fields_and_local_time():
    r = vt.parse(row())
    assert r["source_id"] == "26SB017534" and r["crash_datetime"] == datetime(2026, 11, 13, 14, 17)
    assert (r["latitude"], r["longitude"]) == (44.4429553, -73.20977389)
    assert r["severity"] == "Property Damage Only" and r["injured"] is None and r["killed"] is None
    assert r["road"] == "SHELBURNE RD" and r["crash_type"] == "Rear End" and r["weather"] == "Clear"
    assert r["lighting"] is None and r["hit_and_run"] is None
    assert vt.parse(row(when=1752190200000))["crash_datetime"] == datetime(2025, 7, 10, 23, 30)


def test_labels_road_fallback_and_trimmed_ids():
    r = vt.parse(row(rid=" 19-04169", InjuryType="Fatal", RDFLNAME=None, Weather="Unknown", DirOfCollision=""))
    assert r["source_id"] == "19-04169" and r["severity"] == "Fatal" and r["road"] == "918-938 Shelburne Rd"
    assert r["weather"] is None and r["crash_type"] is None
    assert vt.parse(row(InjuryType=""))["severity"] is None


def test_coordinates_and_duplicate_reports():
    assert vt.parse(row(LATITUDE=None, LONGITUDE=None))["longitude"] == -73.20978
    r = vt.parse(row(LATITUDE=None, LONGITUDE=None, _lat=None, _lon=None))
    assert r["latitude"] is None and r["longitude"] is None
    assert vt.parse(row(LATITUDE=40.0, LONGITUDE=-75.0, _lat=None, _lon=None))["latitude"] is None  # outside VT
    parsed, skipped = base.parse_all(vt.SPEC, [row(), row(REPORTINGAGENCYid="VTVSP0300"), row("X1"), row(rid=None)])
    assert sorted(r["source_id"] for r in parsed) == ["26SB017534", "X1"] and skipped == 1
