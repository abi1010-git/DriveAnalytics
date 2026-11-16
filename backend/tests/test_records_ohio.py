from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import ohio


def row(doc=20259990001, **extra):
    raw = {"OBJECTID": 1, "DOCUMENT_NBR": doc, "CRASH_YR": 2025, "MONTH_OF_CRASH": 7, "DAY_IN_WEEK_CD": 6,
           "HOUR_OF_CRASH": 17, "CRASH_SEVERITY_CD": 3, "CRASH_SEVERITY_TXT": "Minor Injury Suspected",
           "CRASH_TYPE_CD": 6, "CRASH_TYPE_TXT": "Angle", "ODOT_CRASH_LOCATION_TXT": "Four-Way Intersection",
           "COUNTY_CD": "FRA", "ODOT_LATITUDE_NBR": 39.961, "ODOT_LONGITUDE_NBR": -82.999, "NLFID": "SFRAUS00023**C",
           "_lat": 39.9611, "_lon": -82.9991}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["ohio"]
    assert spec is ohio.SPEC and len(spec.urls) == 5 and "month precision" in spec.notes.lower()


def test_parse_month_precision():
    r = ohio.parse(row())
    assert r["source_id"] == "20259990001"
    assert r["crash_datetime"] == datetime(2025, 7, 1, 0, 0)  # first of the month; hour not attached
    assert (r["latitude"], r["longitude"]) == (39.961, -82.999)
    assert r["severity"] == "Minor Injury Suspected" and r["crash_type"] == "Angle"
    assert r["injured"] is None and r["killed"] is None and r["road"] is None and r["hit_and_run"] is None


def test_bad_values():
    assert ohio.parse(row(MONTH_OF_CRASH=13))["crash_datetime"] is None
    assert ohio.parse(row(CRASH_YR=None))["crash_datetime"] is None
    r = ohio.parse(row(ODOT_LATITUDE_NBR=0, ODOT_LONGITUDE_NBR=0))
    assert (r["latitude"], r["longitude"]) == (39.9611, -82.9991)
    r = ohio.parse(row(ODOT_LATITUDE_NBR=0, ODOT_LONGITUDE_NBR=0, _lat=None, _lon=None))
    assert r["latitude"] is None
    parsed, skipped = base.parse_all(ohio.SPEC, [row(), row(doc=None), row(doc=20259990002)])
    assert len(parsed) == 2 and skipped == 1
