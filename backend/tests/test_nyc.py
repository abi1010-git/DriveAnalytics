from datetime import datetime

from sqlalchemy import func, select

from app.models import CrashFlag, NycCrash, NycCrashFactor
from pipeline import nyc
from tests.conftest import nyc_row


def test_parse_record_fields():
    crash, factors = nyc.parse_record(nyc_row(off_street_name="772       EDGEWATER ROAD", vehicle_type_code_3="Bus"))
    assert crash["crash_datetime"] == datetime(2026, 11, 12, 16, 40) and crash["hour"] == 16
    assert crash["persons_injured"] == 1 and crash["pedestrians_injured"] == 1
    assert crash["cross_street"] == "PRESIDENT ST" and crash["off_street"] == "772 EDGEWATER ROAD"
    assert crash["vehicle_types"] == ["Sedan", "Bike", "Bus"]
    assert [f["factor"] for f in factors] == ["Failure to Yield Right-of-Way"]  # "Does Not Apply" dropped


def test_bad_coordinates_and_missing_fields():
    assert nyc.parse_record(nyc_row(latitude="0", longitude="0"))[0]["latitude"] is None
    assert nyc.parse_record(nyc_row(longitude="-201.35999"))[0]["longitude"] is None
    assert nyc.parse_record(nyc_row(latitude=None, longitude=None))[0]["latitude"] is None
    crash, _ = nyc.parse_record(nyc_row(crash_time="25:99"))
    assert crash["hour"] is None and crash["crash_datetime"] == datetime(2026, 11, 12)
    assert nyc.parse_record(nyc_row(collision_id=None)) is None
    assert nyc.parse_record(nyc_row(crash_date=None)) is None


def test_factor_spelling_variants_are_merged():
    assert nyc.canonical_factor("Illnes") == "Illness"
    assert nyc.canonical_factor("Drugs (illegal)") == nyc.canonical_factor("Drugs (Illegal)") == "Drugs (Illegal)"
    assert nyc.canonical_factor("Cell Phone (hand-Held)") == "Cell Phone (Hand-Held)"
    assert nyc.canonical_factor("80") is None and nyc.canonical_factor("Does Not Apply") is None


def test_page_url_uses_keyset_paging():
    url = nyc.page_url("abc", 1000, "2026-11-01")
    assert "collision_id+%3E+%27abc%27" in url and "%3Aupdated_at" in url and "%24order=collision_id" in url
    assert "%24where" not in nyc.page_url(None, 1000, None)


def test_fetch_pages_until_short_page(tmp_path):
    pages = [[nyc_row("a"), nyc_row("b")], [nyc_row("c")]]
    seen = []
    def fake_fetch(url):
        seen.append(url)
        return pages[len(seen) - 1]
    path = nyc.fetch(tmp_path, page_size=2, fetch_page=fake_fetch, log=lambda *_: None)
    assert [r["collision_id"] for r in nyc.iter_raw(path)] == ["a", "b", "c"]
    assert "%27b%27" in seen[1]  # second page starts after the last id of the first


def test_load_file_upserts_and_flags(db, rules, nyc_file):
    first = nyc_file([nyc_row("a"), nyc_row("b", number_of_persons_killed="1", number_of_pedestrians_killed="1",
                                            contributing_factor_vehicle_1="Unsafe Speed", crash_time="2:05"),
                      {"collision_id": "broken"}])
    result = nyc.load_file(db, first, rules.for_source("nyc"), log=lambda *_: None)
    assert result == {"loaded": 2, "skipped": 1, "without_coordinates": 0}
    flags_b = set(db.scalars(select(CrashFlag.flag_id).where(CrashFlag.crash_id == "b")))
    assert flags_b == {"nyc_unsafe_speed", "nyc_pedestrian_harmed", "nyc_fatal", "nyc_late_night"}
    assert set(db.scalars(select(CrashFlag.flag_id).where(CrashFlag.crash_id == "a"))) == {"nyc_right_of_way", "nyc_pedestrian_harmed"}

    # An amended record replaces the old one, and its factors and flags follow.
    update = nyc_file([nyc_row("a", contributing_factor_vehicle_1="Unspecified", number_of_persons_injured="0",
                               number_of_pedestrians_injured="0")], name="update.jsonl.gz")
    nyc.load_file(db, update, rules.for_source("nyc"), scope="since 2026-11-13", log=lambda *_: None)
    assert db.scalar(select(func.count()).select_from(NycCrash)) == 2
    assert db.get(NycCrash, "a").persons_injured == 0
    assert list(db.scalars(select(NycCrashFactor.factor).where(NycCrashFactor.collision_id == "a"))) == ["Unspecified"]
    assert list(db.scalars(select(CrashFlag.flag_id).where(CrashFlag.crash_id == "a"))) == []


def test_duplicate_ids_in_one_batch(db, rules, nyc_file):
    path = nyc_file([nyc_row("a"), nyc_row("a", borough="QUEENS")])
    nyc.load_file(db, path, rules.for_source("nyc"), log=lambda *_: None)
    assert db.get(NycCrash, "a").borough == "QUEENS"
