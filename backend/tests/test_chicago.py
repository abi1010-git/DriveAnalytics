import gzip
import json
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.models import IngestRun, LocalCrash
from pipeline import chicago

ID_A = "a" * 128
ID_B = "b" * 128


def chicago_row(crash_record_id=ID_A, **overrides):
    """A row shaped like the real API output (field names and formats from the live dataset; values invented)."""
    row = {"crash_record_id": crash_record_id, "crash_date": "2026-11-14T23:05:00.000", "posted_speed_limit": "30",
           "weather_condition": "RAIN", "lighting_condition": "DARKNESS, LIGHTED ROAD", "first_crash_type": "PEDESTRIAN",
           "crash_type": "INJURY AND / OR TOW DUE TO CRASH", "prim_contributory_cause": "UNABLE TO DETERMINE",
           "street_no": "4400", "street_direction": "S", "street_name": "KEDZIE AVE", "most_severe_injury": "INCAPACITATING INJURY",
           "injuries_total": "2", "injuries_fatal": "0", "hit_and_run_i": "Y", "latitude": "41.8135", "longitude": "-87.7041",
           "location": {"type": "Point", "coordinates": [-87.7041, 41.8135]}}
    row.update(overrides)
    return {k: v for k, v in row.items() if v is not None}


@pytest.fixture
def raw_file(tmp_path):
    def build(rows, name="crashes.jsonl.gz"):
        path = tmp_path / name
        with gzip.open(path, "wt", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row) + "\n")
        return path
    return build


def test_parse_record_fields():
    row = chicago.parse_record(chicago_row())
    assert row == {
        "source": "chicago", "source_id": ID_A, "crash_datetime": datetime(2026, 11, 14, 23, 5),
        "latitude": 41.8135, "longitude": -87.7041, "road": "4400 S KEDZIE AVE", "injured": 2, "killed": 0,
        "severity": "INCAPACITATING INJURY", "primary_cause": "UNABLE TO DETERMINE", "weather": "RAIN",
        "lighting": "DARKNESS, LIGHTED ROAD", "crash_type": "PEDESTRIAN", "hit_and_run": True,
    }


def test_optional_fields():
    row = chicago.parse_record(chicago_row(hit_and_run_i=None, injuries_total=None, injuries_fatal=None,
                                           street_no=None, street_direction=None, most_severe_injury=None))
    assert row["hit_and_run"] is None and row["injured"] is None and row["killed"] is None
    assert row["road"] == "KEDZIE AVE" and row["severity"] is None
    assert chicago.parse_record(chicago_row(hit_and_run_i="N"))["hit_and_run"] is False
    assert chicago.parse_record(chicago_row(street_name="  W   63RD ST ", street_no=None, street_direction=None))["road"] == "W 63RD ST"


def test_bad_coordinates_and_missing_fields():
    assert chicago.parse_record(chicago_row(latitude="0", longitude="0"))["latitude"] is None
    assert chicago.parse_record(chicago_row(latitude="41.88", longitude="-73.98"))["longitude"] is None  # not Chicago
    assert chicago.parse_record(chicago_row(latitude=None, longitude=None))["latitude"] is None
    assert chicago.parse_record(chicago_row(crash_record_id=None)) is None
    assert chicago.parse_record(chicago_row(crash_record_id="  ")) is None
    assert chicago.parse_record(chicago_row(crash_date=None)) is None
    assert chicago.parse_record(chicago_row(crash_date="not a date")) is None


def test_page_url_uses_keyset_paging():
    url = chicago.page_url("abc", 1000, "2026-11-01")
    assert "crash_record_id+%3E+%27abc%27" in url and "%3Aupdated_at+%3E%3D+%272026-11-01T00%3A00%3A00%27" in url
    assert "%24order=crash_record_id" in url and "%24limit=1000" in url
    assert url.startswith(chicago.DATASET_URL)
    assert "%24where" not in chicago.page_url(None, 1000, None)


def test_fetch_pages_until_short_page(tmp_path):
    pages = [[chicago_row("a"), chicago_row("b")], [chicago_row("c")]]
    seen = []
    def fake_fetch(url):
        seen.append(url)
        return pages[len(seen) - 1]
    path = chicago.fetch(tmp_path, page_size=2, fetch_page=fake_fetch, log=lambda *_: None)
    assert path == tmp_path / "chicago" / "crashes_full.jsonl.gz"
    assert [r["crash_record_id"] for r in chicago.iter_raw(path)] == ["a", "b", "c"]
    assert "%27b%27" in seen[1]  # second page starts after the last id of the first
    # A cached file is reused unless forced.
    assert chicago.fetch(tmp_path, page_size=2, fetch_page=lambda url: pytest.fail("refetched"), log=lambda *_: None) == path


def test_fetch_since_uses_its_own_file(tmp_path):
    path = chicago.fetch(tmp_path, since="2026-11-01", fetch_page=lambda url: [], log=lambda *_: None)
    assert path.name == "crashes_updated_since_2026-11-01.jsonl.gz" and list(chicago.iter_raw(path)) == []


def test_load_file_upserts(db, raw_file):
    first = raw_file([chicago_row(ID_A), chicago_row(ID_B, latitude="0", longitude="0"), {"crash_record_id": "broken"}])
    result = chicago.load_file(db, first, log=lambda *_: None)
    assert result == {"loaded": 2, "skipped": 1, "without_coordinates": 1}
    assert db.get(LocalCrash, ("chicago", ID_A)).injured == 2

    # An amended record replaces the old one in place.
    update = raw_file([chicago_row(ID_A, injuries_total="0", most_severe_injury="NO INDICATION OF INJURY")], name="update.jsonl.gz")
    assert chicago.load_file(db, update, scope="since 2026-11-14", log=lambda *_: None)["loaded"] == 1
    assert db.scalar(select(func.count()).select_from(LocalCrash)) == 2
    crash = db.get(LocalCrash, ("chicago", ID_A))
    assert crash.injured == 0 and crash.severity == "NO INDICATION OF INJURY"
    runs = list(db.scalars(select(IngestRun).where(IngestRun.source == "chicago").order_by(IngestRun.id)))
    assert [(r.scope, r.rows_loaded, r.rows_skipped) for r in runs] == [("full", 2, 1), ("since 2026-11-14", 1, 0)]


def test_duplicate_ids_in_one_batch(db, raw_file):
    path = raw_file([chicago_row(ID_A), chicago_row(ID_A, weather_condition="SNOW")])
    assert chicago.load_file(db, path, log=lambda *_: None)["loaded"] == 1
    assert db.get(LocalCrash, ("chicago", ID_A)).weather == "SNOW"
