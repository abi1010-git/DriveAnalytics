import types
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.models import LiveIncident, LivePoll
from pipeline.live import austin
from pipeline.live.poller import poll_source

NOW = datetime(2026, 11, 16, 6, 0)


def austin_row(rid="A1", issue="Crash Urgent", status="ACTIVE", published="2026-11-16T05:01:56.000Z", updated="2026-11-16T05:01:56.000Z", **extra):
    row = {"traffic_report_id": rid, "published_date": published, "issue_reported": issue, "latitude": "30.2465",
           "longitude": "-97.5935", "address": "3800-4621 Gilbert Rd", "traffic_report_status": status,
           "traffic_report_status_date_time": updated, "agency": "AUSTIN PD"}
    row.update(extra)
    return row


def test_austin_categories_cover_real_labels():
    labels = {"Crash Urgent": "crash", "Crash Service": "crash", "COLLISION": "crash", "COLLISION WITH INJURY": "crash",
              "COLLISN/ LVNG SCN": "crash", "AUTO/ PED": "crash", "COLLISION/PRIVATE PROPERTY": "crash",
              "Traffic Hazard": "hazard", "TRFC HAZD/ DEBRIS": "hazard", "LOOSE LIVESTOCK": "hazard", "Traffic Impediment": "hazard",
              "Stalled Vehicle": "stalled_vehicle", "zSTALLED VEHICLE": "stalled_vehicle", "VEHICLE FIRE": "fire",
              "BLOCKED DRIV/ HWY": "closure", "something new": "other", None: "other"}
    assert {label: austin.category(label) for label in labels} == labels


def test_austin_parse():
    record = austin.parse(austin_row())
    assert record["reported_at"] == datetime(2026, 11, 16, 5, 1, 56)  # Z means UTC
    assert record["category"] == "crash" and record["status"] == "active" and record["latitude"] == 30.2465
    assert austin.parse(austin_row(status="ARCHIVED"))["status"] == "cleared"
    assert austin.parse(austin_row(latitude="0", longitude="0"))["latitude"] is None
    assert austin.parse(austin_row(rid=None)) is None and austin.parse(austin_row(published=None)) is None


def test_austin_pages_and_overlap():
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return [austin_row(f"A{i}") for i in range(austin.PAGE if len(calls) == 1 else 3)]
    rows = austin.fetch(datetime(2026, 11, 16, 5, 0), get)
    assert len(rows) == austin.PAGE + 3 and [c["$offset"] for c in calls] == [["0"], [str(austin.PAGE)]]
    assert "'2026-11-16T03:00:00'" in calls[0]["$where"][0]  # two-hour overlap before `since`


def test_poll_inserts_then_updates_and_resumes(db):
    pages = [[austin_row("A1"), austin_row("A2", issue="Traffic Hazard")],
             [austin_row("A1", status="ARCHIVED", updated="2026-11-16T05:40:00.000Z")]]
    seen_where = []
    def get(url):
        seen_where.append(parse_qs(urlparse(url).query).get("$where", [""])[0])
        return pages[len(seen_where) - 1]

    first = poll_source(db, austin, now=NOW, get=get)
    assert (first.fetched, first.inserted, first.updated, first.error) == (2, 2, 0, None)
    assert "2026-11-09T04:00:00" in seen_where[0]  # first run backfills the default 7 days (minus overlap)

    second = poll_source(db, austin, now=NOW + timedelta(minutes=10), get=get)
    assert (second.inserted, second.updated) == (0, 1)
    assert "2026-11-16T03:01:56" in seen_where[1]  # resumes from newest change held, minus overlap
    a1 = db.get(LiveIncident, ("austin", "A1"))
    assert a1.status == "cleared" and a1.cleared_at == datetime(2026, 11, 16, 5, 40)
    assert a1.first_seen_at == NOW and a1.last_seen_at == NOW + timedelta(minutes=10)
    assert db.get(LiveIncident, ("austin", "A2")).status == "active"  # incremental feed: absence means nothing


def fake_snapshot_adapter(batches):
    calls = iter(batches)
    return types.SimpleNamespace(
        SOURCE="state511", LABEL="Test 511", SNAPSHOT=True,
        fetch=lambda since, get: next(calls),
        parse=lambda raw: {"source_id": raw, "category": "crash", "raw_type": "Crash", "description": None, "road": "I-1",
                           "latitude": 1.0, "longitude": 2.0, "reported_at": NOW, "updated_at": None, "status": "active"})


def test_snapshot_feed_clears_missing_incidents(db):
    adapter = fake_snapshot_adapter([["X", "Y"], ["Y"]])
    poll_source(db, adapter, now=NOW)
    poll = poll_source(db, adapter, now=NOW + timedelta(minutes=10))
    assert poll.cleared == 1
    x, y = db.get(LiveIncident, ("state511", "X")), db.get(LiveIncident, ("state511", "Y"))
    assert (x.status, x.cleared_at) == ("cleared", NOW + timedelta(minutes=10)) and y.status == "active"


def test_feed_error_is_recorded_not_raised(db):
    def boom(url):
        raise TimeoutError("feed down")
    poll = poll_source(db, austin, now=NOW, get=boom)
    assert poll.error == "TimeoutError: feed down"
    assert db.scalar(select(LivePoll.error)) == "TimeoutError: feed down"


def test_live_api(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.routes import live as live_routes

    poll_source(db, austin, now=NOW, get=lambda url: [austin_row("A1"), austin_row("A2", issue="Traffic Hazard"),
                                                     austin_row("OLD", published="2026-11-10T00:00:00.000Z", updated="2026-11-10T01:00:00.000Z")])
    monkeypatch.setattr(live_routes, "_now", lambda: NOW)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        rows = client.get("/api/live/incidents", params={"hours": 6}).json()
        assert {r["id"] for r in rows} == {"A1", "A2"}
        assert [r["id"] for r in client.get("/api/live/incidents", params={"category": "crash"}).json()] == ["A1"]
        source = client.get("/api/live/sources").json()[0]
        assert source["source"] == "austin" and source["crashes_24h"] == 1 and source["incidents_24h"] == 2 and source["last_error"] is None
    finally:
        app.dependency_overrides.clear()
