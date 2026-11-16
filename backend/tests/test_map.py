import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from pipeline import fars
from tests.conftest import accident, vehicle


@pytest.fixture
def client(db, rules, fars_zip):
    crashes = [
        accident(ST_CASE="10001", COUNTY="125", COUNTYNAME="TUSCALOOSA (125)", CITY="5", CITYNAME="TUSCALOOSA", TWAY_ID="I-20", FATALS="2"),
        accident(ST_CASE="10002", COUNTY="125", COUNTYNAME="TUSCALOOSA (125)", CITY="5", CITYNAME="TUSCALOOSA", TWAY_ID="I-20", HOUR="23", PEDS="1"),
        accident(ST_CASE="10003", COUNTY="73", COUNTYNAME="JEFFERSON (73)", CITY="7", CITYNAME="BIRMINGHAM", TWAY_ID="US-31", LATITUDE="77.77770000"),
        accident(STATE="6", STATENAME="California", ST_CASE="60001", COUNTY="37", COUNTYNAME="LOS ANGELES (37)", TWAY_ID="I-5"),
    ]
    fars.load_year(db, fars_zip(crashes, [vehicle(10001, SPEEDREL="3"), vehicle(10002, DR_DRINK="1")]), 2024, rules.for_source("fars"))
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_states_ranked_by_deaths(client):
    rows = client.get("/api/map/states").json()
    assert [(r["state_code"], r["name"], r["crashes"], r["deaths"]) for r in rows] == [(1, "Alabama", 3, 4), (6, "California", 1, 1)]


def test_counties_have_fips(client):
    rows = client.get("/api/map/counties", params={"state_code": 1}).json()
    assert [(r["fips"], r["name"], r["deaths"]) for r in rows] == [("01125", "TUSCALOOSA", 3), ("01073", "JEFFERSON", 1)]


def test_cities(client):
    rows = client.get("/api/map/cities", params={"state_code": 1}).json()
    assert [(r["name"], r["crashes"]) for r in rows] == [("TUSCALOOSA", 2), ("BIRMINGHAM", 1)]
    assert rows[1]["latitude"] is None  # its only crash has an unknown location


def test_summary_for_a_city(client):
    body = client.get("/api/map/summary", params={"state_code": 1, "city": "TUSCALOOSA"}).json()
    assert body["roads"] == [{"road_route": "I-20", "name": "I-20", "crashes": 2, "deaths": 3, "speeding_crashes": 1, "drinking_crashes": 1, "non_motorist_crashes": 1}]
    flags = {f["flag_id"]: f["crashes"] for f in body["factors"]["flags"]}
    assert body["factors"]["total_crashes"] == 2 and body["factors"]["total_deaths"] == 3 and flags["fars_speeding"] == 1 and flags["fars_multiple_fatalities"] == 1
    assert len(body["hours"]) == 24 and body["hours"][10]["crashes"] == 1 and body["hours"][23]["crashes"] == 1


def test_crash_points_skip_unknown_locations(client):
    rows = client.get("/api/map/crashes", params={"state_code": 1}).json()
    assert {r["id"] for r in rows} == {"2024-10001", "2024-10002"}
    assert client.get("/api/map/crashes", params={"state_code": 1, "county_code": 73}).json() == []
