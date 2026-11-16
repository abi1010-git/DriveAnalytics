from datetime import date

from sqlalchemy import func, select

from app.models import CrashFlag, FarsCrash, IngestRun
from pipeline import fars
from tests.conftest import accident, vehicle


def test_parse_accident_basic_fields():
    record = fars.parse_accident(accident(), 2024)
    assert record["id"] == "2024-10001"
    assert record["crash_date"] == date(2024, 1, 1)
    assert (record["hour"], record["minute"]) == (10, 30)
    assert record["county_name"] == "TUSCALOOSA"  # "(125)" code suffix removed
    assert record["city_name"] is None  # CITY 0 / NOT APPLICABLE
    assert record["latitude"] == 33.47131111 and record["longitude"] == -87.49670278
    assert record["weather"] == "Clear" and record["junction"] == "Non-Junction"
    assert record["cross_road_name"] is None


def test_placeholder_place_names_become_null():
    for name in ("Other", "Not Reported", "UNKNOWN"):
        assert fars.parse_accident(accident(CITY="9997", CITYNAME=name), 2024)["city_name"] is None
    assert fars.parse_accident(accident(COUNTY="999", COUNTYNAME="Unknown (999)"), 2024)["county_name"] is None
    assert fars.parse_accident(accident(CITY="1", CITYNAME="CROTHERSVILLE"), 2024)["city_name"] == "CROTHERSVILLE"


def test_unknown_codes_become_null():
    record = fars.parse_accident(accident(LATITUDE="77.77770000", LONGITUD="777.777700000", HOUR="99", MINUTE="99", DAY="99"), 2024)
    assert record["latitude"] is None and record["longitude"] is None
    assert record["hour"] is None and record["minute"] is None
    assert record["crash_date"] is None
    assert fars.parse_accident(accident(LATITUDE="99.99990000", LONGITUD="-87.5"), 2024)["latitude"] is None


def test_vehicle_rollup_speeding_drinking_and_limit():
    rollup = fars.vehicle_rollup([
        vehicle(1, SPEEDREL="0", VSPD_LIM="45"),
        vehicle(1, VEH_NO="2", SPEEDREL="4", DR_DRINK="1", VSPD_LIM="55"),
        vehicle(2, SPEEDREL="9", VSPD_LIM="99"),  # unknown speeding, unknown limit
        vehicle(3, SPEEDREL="8", VSPD_LIM="0"),  # no driver present, no statutory limit
    ])
    assert rollup[1] == {"speeding_involved": True, "drinking_driver_involved": True, "max_speed_limit_mph": 55}
    assert rollup[2] == {"speeding_involved": False, "drinking_driver_involved": False, "max_speed_limit_mph": None}
    assert rollup[3]["max_speed_limit_mph"] is None


def test_cp1252_archive_is_read(fars_zip):
    path = fars_zip([accident(CITY="1294", CITYNAME="LA CAÑADA FLINTRIDGE")], [vehicle(10001)], encoding="cp1252")
    assert fars.parse_year(path, 2024)[0]["city_name"] == "LA CAÑADA FLINTRIDGE"


def test_load_year_is_repeatable_and_flags_crashes(db, rules, fars_zip):
    path = fars_zip(
        [accident(), accident(ST_CASE="10002", LGT_COND="2", LGT_CONDNAME="Dark - Not Lighted", HOUR="2", PEDS="1", FATALS="2")],
        [vehicle(10001), vehicle(10002, SPEEDREL="3", DR_DRINK="1", VSPD_LIM="65")],
    )
    for _ in range(2):  # second run must replace, not duplicate
        assert fars.load_year(db, path, 2024, rules.for_source("fars")) == 2
    assert db.scalar(select(func.count()).select_from(FarsCrash)) == 2
    flags = set(db.scalars(select(CrashFlag.flag_id).where(CrashFlag.crash_id == "2024-10002")))
    assert flags == {"fars_speeding", "fars_drinking_driver", "fars_dark_unlit", "fars_high_speed_road",
                     "fars_non_motorist", "fars_late_night", "fars_multiple_fatalities"}
    assert set(db.scalars(select(CrashFlag.flag_id).where(CrashFlag.crash_id == "2024-10001"))) == set()
    assert db.scalar(select(func.count()).select_from(IngestRun)) == 2


def test_load_year_leaves_other_years_alone(db, rules, fars_zip):
    fars.load_year(db, fars_zip([accident()], [vehicle(10001)], year=2023), 2023, rules.for_source("fars"))
    fars.load_year(db, fars_zip([accident()], [vehicle(10001)], year=2024), 2024, rules.for_source("fars"))
    assert sorted(db.scalars(select(FarsCrash.id))) == ["2023-10001", "2024-10001"]


def test_route_key_groups_the_same_road():
    cases = {
        "I-45": "I-45", "I-45/NORTH FWY": "I-45", "I-45/GULF FWY": "I-45",
        "SR-3 GRATIOT AVE": "SR-3", "SR- 31": "SR-31", "SR-7   E BASELINE RD": "SR-7", "US-31E NEW GLASGOW RD": "US-31E",
        "FM 1093/WESTHEIMER RD": "FM-1093", "FM 379": "FM-379",
        "MU-COIT RD": "COIT RD", "CR-TUCKER RD": "TUCKER RD", "CR-C": "CR-C", "CR-B40/390TH": "CR-B40",
        "university blvd": "UNIVERSITY BLVD", "": None, None: None,
    }
    assert {name: fars.route_key(name) for name in cases} == cases
