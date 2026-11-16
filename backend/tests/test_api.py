import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from pipeline import fars, nyc
from tests.conftest import accident, nyc_row, vehicle


@pytest.fixture
def client(db, rules, fars_zip, nyc_file):
    fars.load_year(db, fars_zip([accident(), accident(ST_CASE="10002", LATITUDE="40.0", LONGITUD="-75.0", HOUR="2")],
                                [vehicle(10001, SPEEDREL="3"), vehicle(10002)]), 2024, rules.for_source("fars"))
    nyc.load_file(db, nyc_file([nyc_row("a"), nyc_row("b", borough="QUEENS", latitude=None, longitude=None)]),
                  rules.for_source("nyc"), log=lambda *_: None)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_datasets(client):
    body = client.get("/api/datasets").json()
    assert body["fars"]["years"] == [{"year": 2024, "crashes": 2, "fatalities": 2}]
    assert body["nyc"]["crashes"] == 2 and body["nyc"]["with_coordinates"] == 1
    assert body["nyc"]["last_loaded"] is not None


def test_risk_flag_counts(client):
    counts = {f["id"]: f["crashes_flagged"] for f in client.get("/api/risk-flags").json()}
    assert counts["fars_speeding"] == 1 and counts["fars_late_night"] == 1 and counts["nyc_pedestrian_harmed"] == 2


def test_fars_filters(client):
    assert [c["id"] for c in client.get("/api/fars/crashes", params={"flag": "fars_speeding"}).json()] == ["2024-10001"]
    in_box = client.get("/api/fars/crashes", params={"bbox": "-76,39,-74,41"}).json()
    assert [c["id"] for c in in_box] == ["2024-10002"] and in_box[0]["flags"] == ["fars_late_night"]
    assert client.get("/api/fars/crashes", params={"bbox": "nope"}).status_code == 422


def test_nyc_listing(client):
    rows = client.get("/api/nyc/crashes", params={"borough": "brooklyn"}).json()
    assert [r["collision_id"] for r in rows] == ["a"]
    assert rows[0]["contributing_factors"] == ["Failure to Yield Right-of-Way"]
    assert set(rows[0]["flags"]) == {"nyc_right_of_way", "nyc_pedestrian_harmed"}
