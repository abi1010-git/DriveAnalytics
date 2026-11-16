import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from app.models import LiveIncident
from pipeline.live import sf
from pipeline.live.poller import poll_source

NOW = datetime(2026, 11, 16, 6, 0)

# Two rows as served by data.sf.gov (trimmed), times in Pacific local without a zone.
FEED = r"""[
 {"id":"41970833","cad_number":"263192671","received_datetime":"2026-11-15T19:33:50.000","close_datetime":"2026-11-15T19:53:31.000",
  "call_type_final":"519","call_type_final_desc":"INJURY VEH ACCIDENT","priority_final":"A","agency":"Police","disposition":"HAN",
  "sensitive_call":false,"intersection_name":"06TH AVE \\ BALBOA ST",
  "intersection_point":{"type":"Point","coordinates":[-122.464010601,37.777234779]},"police_district":"RICHMOND",
  "call_last_updated_at":"2026-11-15T20:10:35.000","data_as_of":"2026-11-15T21:44:09.000"},
 {"id":"41969593","cad_number":"263192492","received_datetime":"2026-11-15T18:13:28.000",
  "call_type_final":"586","call_type_final_desc":"TRAFFIC HAZARD","priority_final":"B","agency":"Police",
  "sensitive_call":false,"intersection_name":"13TH ST \\ SOUTH VAN NESS AVE",
  "intersection_point":{"type":"Point","coordinates":[-122.417753194,37.769815079]},"police_district":"MISSION",
  "call_last_updated_at":"2026-11-15T18:20:03.000","data_as_of":"2026-11-15T21:44:09.000"}
]"""


def sf_row(cad="263192671", **extra):
    row = dict(json.loads(FEED)[0], cad_number=cad)
    row.update(extra)
    return {k: v for k, v in row.items() if v is not None}


def test_sf_parse():
    crash, hazard = (sf.parse(r) for r in json.loads(FEED))
    assert crash["source_id"] == "263192671" and crash["category"] == "crash" and crash["raw_type"] == "519 INJURY VEH ACCIDENT"
    assert crash["road"] == "06TH AVE & BALBOA ST" and crash["description"] == "Priority A, Richmond district, disposition HAN"
    assert (crash["latitude"], crash["longitude"]) == (37.777234779, -122.464010601)  # GeoJSON is [lon, lat]
    assert crash["reported_at"] == datetime(2026, 11, 16, 3, 33, 50)  # 19:33 PST = 03:33 UTC next day
    assert crash["updated_at"] == datetime(2026, 11, 16, 4, 10, 35) and crash["status"] == "cleared"
    assert hazard["category"] == "hazard" and hazard["status"] == "active"  # no close time, no disposition
    assert hazard["updated_at"] == datetime(2026, 11, 16, 2, 20, 3)


def test_sf_coordinates_and_required_fields():
    assert sf.parse(sf_row(intersection_point=None))["latitude"] is None  # sensitive calls carry no location
    outside = sf.parse(sf_row(intersection_point={"type": "Point", "coordinates": [-118.24, 34.05]}))
    assert (outside["latitude"], outside["longitude"]) == (None, None)
    assert sf.parse(sf_row(intersection_point={"type": "Point", "coordinates": []}))["latitude"] is None
    assert sf.parse(sf_row(cad=None, id=None)) is None and sf.parse(sf_row(received_datetime=None)) is None
    assert sf.parse(sf_row(cad=None))["source_id"] == "41970833"  # falls back to the row id


def test_sf_pacific_time():
    assert sf.pacific_to_utc("2026-07-04T12:00:00.000") == datetime(2026, 7, 4, 19, 0)  # PDT
    assert sf.pacific_to_utc("2026-12-01T12:00:00.000") == datetime(2026, 12, 1, 20, 0)  # PST
    assert sf.pacific_to_utc("2026-03-08T03:30:00") == datetime(2026, 3, 8, 10, 30)  # just after spring forward
    assert sf.pacific_to_utc("2026-11-01T00:30:00") == datetime(2026, 11, 1, 7, 30)  # before fall back
    assert sf.pacific_to_utc("2026-11-01T03:00:00") == datetime(2026, 11, 1, 11, 0)
    assert sf.pacific_to_utc(None) is None and sf.pacific_to_utc("garbage") is None
    assert sf.utc_to_pacific(datetime(2026, 11, 16, 3, 33, 50)) == datetime(2026, 11, 15, 19, 33, 50)
    assert sf.utc_to_pacific(datetime(2026, 7, 4, 19, 0)) == datetime(2026, 7, 4, 12, 0)


def test_sf_categories():
    codes = {"518": "crash", "518HR": "crash", "518HRL": "crash", "519": "crash", "519HR": "crash",
             "586": "hazard", "585": "other", None: "other"}
    assert {code: sf.category(code) for code in codes} == codes


def test_sf_query_filters_call_types_pages_and_overlaps():
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return json.dumps([sf_row(f"C{len(calls)}-{i}") for i in range(sf.PAGE if len(calls) == 1 else 3)])
    rows = sf.fetch(datetime(2026, 11, 16, 5, 0), get)
    assert len(rows) == sf.PAGE + 3 and [c["$offset"] for c in calls] == [["0"], [str(sf.PAGE)]]
    where = calls[0]["$where"][0]
    assert "call_type_final like '518%'" in where and "call_type_final like '519%'" in where and "call_type_final = '586'" in where
    assert "call_last_updated_at >= '2026-11-15T19:00:00'" in where  # 05:00 UTC minus 2 h overlap, in Pacific time
    assert "received_datetime" not in parse_qs(urlparse(sf.page_url(None, 0)).query)["$where"][0]


def test_sf_fetch_dedupes_calls_keeping_latest():
    rows = [sf_row("X", call_last_updated_at="2026-11-15T20:00:00.000", disposition=None, close_datetime=None),
            sf_row("X", call_last_updated_at="2026-11-15T20:30:00.000"),
            sf_row("X", call_last_updated_at="2026-11-15T19:00:00.000"),
            sf_row("Y")]
    fetched = sf.fetch(None, lambda url: json.dumps(rows))
    assert len(fetched) == 2
    assert next(r for r in fetched if r["cad_number"] == "X")["call_last_updated_at"] == "2026-11-15T20:30:00.000"


def test_sf_poll_keeps_rows_that_roll_off(db):
    pages = [FEED, json.dumps([dict(json.loads(FEED)[1], close_datetime="2026-11-15T18:40:00.000",
                                         call_last_updated_at="2026-11-15T18:40:05.000")])]
    seen = []
    def get(url):
        seen.append(parse_qs(urlparse(url).query)["$where"][0])
        return pages[len(seen) - 1]

    first = poll_source(db, sf, now=NOW, get=get)
    assert (first.fetched, first.inserted, first.error) == (2, 2, None)
    assert "2026-11-08T20:00:00" in seen[0]  # 7-day backfill minus overlap, in Pacific time

    second = poll_source(db, sf, now=NOW + timedelta(minutes=10), get=get)
    assert (second.inserted, second.updated, second.cleared) == (0, 1, 0)
    assert "2026-11-15T18:10:35" in seen[1]  # newest change held (04:10:35 UTC) minus overlap, in Pacific time
    hazard = db.get(LiveIncident, ("sf", "263192492"))
    assert hazard.status == "cleared" and hazard.cleared_at == datetime(2026, 11, 16, 2, 40, 5)
    assert db.get(LiveIncident, ("sf", "263192671")).status == "cleared"  # absent from the 2nd fetch, still kept
