from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import maine


def row(crash_id="2026-30473", when=1794529320000, **extra):
    # 1794529320000 = 2026-11-13 00:22 UTC = 2026-11-12 19:22 in Maine (ACCIDENT_TIME)
    raw = {"OBJECTID": 1, "CRASH_ID": crash_id, "REPORT_NUMBER": "26-079879", "ACCIDENT_DATE": 1794459600000,
           "ACCIDENT_DATE_TIME": when, "ACCIDENT_TIME": "19:22:00", "ACCIDENT_HOUR": 19, "INJURY_LEVEL": "B",
           "INJURY_LEVEL_CODE": 3, "INJURY_COUNT": 3, "NO_OF_K_INJ": 0, "NO_OF_A_INJ": 0, "NO_OF_B_INJ": 1,
           "NO_OF_C_INJ": 2, "LATITUDE": 44.81429786, "LONGITUDE": -68.80457456, "PRIMARY_ROUTE_NAME": "ST RTE 222",
           "TYPE_OF_CRASH_DESCR": "Rear End / Sideswipe", "WEATHER_CONDITION_DESCR": "Clear",
           "LIGHT_CONDITION_DESCR": "Dark - Lighted", "_lat": 44.8143, "_lon": -68.8046}
    raw.update(extra)
    return raw


def test_registered():
    assert records.all_specs()["maine"] is maine.SPEC and not maine.SPEC.epoch_is_local


def test_parse_fields_and_utc_time():
    r = maine.parse(row())
    assert r["source_id"] == "2026-30473"
    assert r["crash_datetime"] == datetime(2026, 11, 12, 19, 22)  # UTC converted to Eastern = ACCIDENT_TIME
    assert (r["latitude"], r["longitude"]) == (44.81429786, -68.80457456)
    assert r["injured"] == 3 and r["killed"] == 0 and r["severity"] == "Suspected Minor Injury (B)"
    assert r["road"] == "ST RTE 222" and r["crash_type"] == "Rear End / Sideswipe"
    assert r["weather"] == "Clear" and r["lighting"] == "Dark - Lighted" and r["hit_and_run"] is None


def test_summer_time_uses_daylight_offset():
    # 2025-07-28 01:40 UTC = 2025-07-27 21:40 EDT
    assert maine.parse(row(when=1753666800000))["crash_datetime"] == datetime(2025, 7, 27, 21, 40)


def test_fatal_excludes_k_from_injured_and_maps_levels():
    r = maine.parse(row(INJURY_LEVEL="K", INJURY_COUNT=3, NO_OF_K_INJ=1, NO_OF_A_INJ=1, NO_OF_B_INJ=0, NO_OF_C_INJ=1))
    assert r["killed"] == 1 and r["injured"] == 2 and r["severity"] == "Fatal (K)"
    r = maine.parse(row(INJURY_LEVEL="PD", NO_OF_B_INJ=0, NO_OF_C_INJ=0, LIGHT_CONDITION_DESCR="Unknown"))
    assert r["severity"] == "Property Damage Only" and r["injured"] == 0 and r["lighting"] is None
    r = maine.parse(row(NO_OF_A_INJ=None, NO_OF_B_INJ=None, NO_OF_C_INJ=None, INJURY_LEVEL=None))
    assert r["injured"] is None and r["severity"] is None


def test_coordinates_and_duplicates():
    assert maine.parse(row(LATITUDE=None, LONGITUDE=None))["latitude"] == 44.8143
    r = maine.parse(row(LATITUDE=0, LONGITUDE=0, _lat=None, _lon=None))
    assert r["latitude"] is None and r["longitude"] is None
    parsed, skipped = base.parse_all(maine.SPEC, [row(), row(OBJECTID=2), row("2026-30474"), row(when=None)])
    assert sorted(r["source_id"] for r in parsed) == ["2026-30473", "2026-30474"] and skipped == 1
