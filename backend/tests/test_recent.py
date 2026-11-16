import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import LocalCrash
from pipeline import nyc
from pipeline.live import austin
from pipeline.live.poller import poll_source
from tests.conftest import nyc_row
from tests.test_live import austin_row


@pytest.fixture
def client(db, rules, nyc_file):
    nyc.load_file(db, nyc_file([nyc_row("n1"), nyc_row("n2", crash_date="2025-03-02T00:00:00.000", number_of_persons_killed="1"),
                                nyc_row("n3", latitude=None, longitude=None)]), rules.for_source("nyc"), log=lambda *_: None)
    db.add(LocalCrash(source="chicago", source_id="c1", crash_datetime=datetime(2026, 11, 14, 8, 30), latitude=41.88, longitude=-87.63,
                      road="W MADISON ST", injured=2, killed=0, crash_type="REAR END"))
    db.commit()
    poll_source(db, austin, now=datetime(2026, 11, 16, 6), get=lambda url: json.dumps([austin_row("a1"), austin_row("a2", issue="Traffic Hazard")]))
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_summary_counts_per_source(client):
    rows = {r["source"]: r for r in client.get("/api/recent/summary").json()}
    assert rows["nyc"]["count"] == 3 and rows["nyc"]["killed"] == 1 and rows["nyc"]["with_coordinates"] == 2
    assert rows["chicago"]["kind"] == "record" and rows["chicago"]["injured"] == 2
    assert rows["austin"]["kind"] == "live" and rows["austin"]["count"] == 1  # the hazard is not a crash
    assert {r["source"]: r for r in client.get("/api/recent/summary", params={"all_incidents": True}).json()}["austin"]["count"] == 2


def test_window_filters(client):
    rows = {r["source"]: r["count"] for r in client.get("/api/recent/summary", params={"start": "2026-01-01"}).json()}
    assert rows == {"nyc": 2, "chicago": 1, "austin": 1}
    chicago_box = "-87.95,41.64,-87.52,42.03"
    assert [r["source"] for r in client.get("/api/recent/summary", params={"bbox": chicago_box}).json()] == ["chicago"]


def test_points_need_bbox_and_skip_unlocated(client):
    assert client.get("/api/recent/points").status_code == 422
    rows = client.get("/api/recent/points", params={"bbox": "-74.3,40.4,-73.6,41"}).json()
    assert sorted(r["id"] for r in rows) == ["n1", "n2"] and rows[0]["time"] > rows[1]["time"]


def test_monthly(client):
    rows = client.get("/api/recent/monthly").json()
    assert {"source": "nyc", "month": "2025-03", "count": 1} in rows and {"source": "chicago", "month": "2026-11", "count": 1} in rows


def test_window_accepts_datetimes_with_zone(client):
    rows = {r["source"]: r["count"] for r in client.get("/api/recent/summary", params={"start": "2026-11-16T04:00:00Z", "all_incidents": True}).json()}
    assert rows == {"austin": 2}
