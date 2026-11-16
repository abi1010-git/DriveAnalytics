import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.models import LiveIncident
from pipeline.live import seattle
from pipeline.live.poller import poll_source

NOW = datetime(2026, 11, 16, 6, 0)


def seattle_row(num="F260164571", kind="MVI Freeway", when="2026-11-15T21:44:00.000", **extra):
    row = {"address": "Aurora Ave N / Crockett St", "type": kind, "datetime": when, "latitude": "47.637464",
           "longitude": "-122.344264", "report_location": {"type": "Point", "coordinates": [-122.344264, 47.637464]},
           "incident_number": num}
    row.update(extra)
    return row


def test_seattle_categories():
    assert {seattle.parse(seattle_row(kind=k))["category"] for k in seattle.CRASH_TYPES} == {"crash"}
    assert {seattle.parse(seattle_row(kind=k))["category"] for k in seattle.FIRE_TYPES} == {"fire"}
    assert seattle.parse(seattle_row(kind="Aid Response")) is None  # not a traffic call


def test_seattle_parse():
    record = seattle.parse(seattle_row())
    assert record["reported_at"] == datetime(2026, 11, 16, 5, 44)  # 21:44 PST = 05:44 UTC next day
    assert record["updated_at"] == record["reported_at"] and record["status"] == "cleared"
    assert (record["source_id"], record["raw_type"], record["road"]) == ("F260164571", "MVI Freeway", "Aurora Ave N / Crockett St")
    assert (record["latitude"], record["longitude"]) == (47.637464, -122.344264)
    assert seattle.parse(seattle_row(latitude="0", longitude="0"))["latitude"] is None
    assert seattle.parse(seattle_row(latitude=None, longitude=None))["longitude"] is None
    assert seattle.parse(seattle_row(num=None)) is None and seattle.parse(seattle_row(when=None)) is None
    assert seattle.parse(seattle_row(when="garbage")) is None


@pytest.mark.parametrize("local, utc", [
    ("2026-07-04T12:00:00.000", datetime(2026, 7, 4, 19, 0)),     # PDT, UTC-7
    ("2026-01-15T12:00:00.000", datetime(2026, 1, 15, 20, 0)),    # PST, UTC-8
    ("2026-03-08T01:59:00.000", datetime(2026, 3, 8, 9, 59)),     # just before spring forward
    ("2026-03-08T03:00:00.000", datetime(2026, 3, 8, 10, 0)),     # just after
    ("2026-11-01T00:30:00.000", datetime(2026, 11, 1, 7, 30)),    # still PDT
    ("2026-11-01T02:30:00.000", datetime(2026, 11, 1, 10, 30)),   # back to PST
    ("2005-04-02T12:00:00.000", datetime(2005, 4, 2, 20, 0)),     # pre-2007 rules: DST began Apr 3
    ("2005-10-29T12:00:00.000", datetime(2005, 10, 29, 19, 0)),   # pre-2007 rules: DST ended Oct 30
])
def test_seattle_timezone(local, utc):
    assert seattle.parse(seattle_row(when=local))["reported_at"] == utc
    assert seattle.to_pacific(utc) == datetime.fromisoformat(local)



def test_seattle_query_filters_types_and_converts_since():
    query = parse_qs(urlparse(seattle.page_url(datetime(2026, 7, 4, 19, 0), 0)).query)
    where = query["$where"][0]
    assert "'MVI - Motor Vehicle Incident'" in where and "'Car Fire Freeway'" in where and "'Aid Response'" not in where
    assert "datetime >= '2026-07-04T11:00:00'" in where  # 19:00 UTC minus 1h overlap = 11:00 PDT
    winter = parse_qs(urlparse(seattle.page_url(datetime(2026, 1, 15, 20, 0), 0)).query)["$where"][0]
    assert "datetime >= '2026-01-15T11:00:00'" in winter  # PST
    assert query["$order"] == ["datetime, incident_number"]
    assert "datetime >=" not in parse_qs(urlparse(seattle.page_url(None, 0)).query)["$where"][0]


def test_seattle_pages(monkeypatch):
    monkeypatch.setattr(seattle, "PAGE", 3)
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return json.dumps([seattle_row(f"F{len(calls)}{i}") for i in range(3 if len(calls) < 3 else 1)])
    rows = seattle.fetch(datetime(2003, 1, 1), get)
    assert len(rows) == 7 and [c["$offset"] for c in calls] == [["0"], ["3"], ["6"]]
    assert all(c["$limit"] == ["3"] for c in calls)
    assert len({c["$where"][0] for c in calls}) == 1  # same filter on every page


def test_seattle_poll(db):
    pages = [[seattle_row("F1"), seattle_row("F2", kind="Car Fire", when="2026-11-15T21:50:00.000"),
              seattle_row("F3", kind="Aid Response")],
             [seattle_row("F2", kind="Car Fire", when="2026-11-15T21:50:00.000"), seattle_row("F4", when="2026-11-15T22:05:00.000")]]
    seen_where = []
    def get(url):
        seen_where.append(parse_qs(urlparse(url).query)["$where"][0])
        return json.dumps(pages[len(seen_where) - 1])

    first = poll_source(db, seattle, now=NOW, get=get)
    assert (first.fetched, first.inserted, first.updated, first.error) == (2, 2, 0, None)
    assert "datetime >= '2026-11-08T21:00:00'" in seen_where[0]  # 7-day backfill minus 1h, in PST

    second = poll_source(db, seattle, now=NOW + timedelta(minutes=10), get=get)
    assert (second.fetched, second.inserted, second.updated) == (2, 1, 0)
    assert "datetime >= '2026-11-15T20:50:00'" in seen_where[1]  # newest held (21:50 PST) minus overlap
    f2 = db.get(LiveIncident, ("seattle", "F2"))
    assert (f2.category, f2.status, f2.cleared_at) == ("fire", "cleared", datetime(2026, 11, 16, 5, 50))
    assert db.get(LiveIncident, ("seattle", "F4")).reported_at == datetime(2026, 11, 16, 6, 5)
