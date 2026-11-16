from datetime import datetime
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select

from app.models import LocalCrash
from pipeline import records
from pipeline.records import base
from pipeline.records.sources import montgomery_md as mc


def mc_row(rid="MCP1", when="2026-11-11T03:19:00.000", **extra):
    row = {"report_number": rid, "acrs_report_type": "Injury Crash", "crash_date_time": when, "hit_run": "No",
           "road_name": "SENECA CREEK TRL", "collision_type": "Single Vehicle", "weather": "Clear",
           "light": "Dark - Not Lighted", "latitude": "39.13209967", "longitude": "-77.2679315"}
    row.update(extra)
    return row


def test_registry_finds_specs():
    assert "montgomery_md" in records.all_specs()


def test_montgomery_parse():
    record = mc.parse(mc_row())
    assert record["crash_datetime"] == datetime(2026, 11, 11, 3, 19) and record["latitude"] == 39.13209967
    assert record["severity"] == "Injury Crash" and record["injured"] is None and record["hit_and_run"] is False
    assert mc.parse(mc_row(latitude="0", longitude="0"))["latitude"] is None
    assert mc.parse(mc_row(when="1825-01-01T00:00:00"))["crash_datetime"] is None


def test_helpers():
    spec = mc.SPEC
    assert base.epoch(spec, 1794787200000) == datetime(2026, 11, 15, 19, 0)  # 2026-11-16 00:00 UTC in New York
    local = base.SourceSpec(**{**spec.__dict__, "epoch_is_local": True})
    assert base.epoch(local, 1794787200000) == datetime(2026, 11, 16, 0, 0)
    assert base.number("3.0") == 3 and base.number("-1") == 0 and base.number(None) is None
    assert base.text("  A   B ") == "A B" and base.text("") is None


def test_socrata_paging_and_since(tmp_path):
    spec = base.SourceSpec(**{**mc.SPEC.__dict__, "page_size": 2})
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return [mc_row("A"), mc_row("B")] if len(calls) == 1 else [mc_row("C")]
    path = base.fetch(spec, datetime(2026, 11, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    assert [r["report_number"] for r in base.iter_raw(path)] == ["A", "B", "C"]
    assert calls[1]["$offset"] == ["2"] and "crash_date_time >= '2026-11-01T00:00:00'" in calls[0]["$where"][0]


def test_arcgis_paging_merges_geometry(tmp_path):
    spec = base.SourceSpec(source="t", label="T", platform="arcgis", url="https://x/FeatureServer/0", date_field="D",
                           parse=lambda r: r, states=[1], bbox=(-180, -90, 180, 90), page_size=2)
    bodies = [{"features": [{"attributes": {"ID": 1}, "geometry": {"x": -77.1, "y": 39.1}}, {"attributes": {"ID": 2}}],
               "exceededTransferLimit": True},
              {"features": [{"attributes": {"ID": 3}, "geometry": {"x": -77.2, "y": 39.2}}]}]
    calls = []
    def get(url):
        calls.append(parse_qs(urlparse(url).query))
        return bodies[len(calls) - 1]
    rows = list(base.iter_raw(base.fetch(spec, None, raw_dir=tmp_path, get=get, log=lambda *_: None)))
    assert [r["ID"] for r in rows] == [1, 2, 3] and rows[0]["_lat"] == 39.1 and rows[1]["_lat"] is None
    assert calls[1]["resultOffset"] == ["2"] and calls[0]["outSR"] == ["4326"] and calls[0]["where"] == ["1=1"]


def test_update_full_then_incremental_with_dedupe(db, tmp_path):
    spec = base.SourceSpec(**{**mc.SPEC.__dict__, "reduce": lambda rows: {**rows[0], "road": "+".join(r["road"] for r in rows)}})
    pages = [[mc_row("A", when="2026-11-01T10:00:00"), mc_row("B"), mc_row("B", road_name="OTHER RD")],
             [mc_row("B", acrs_report_type="Fatal Crash")]]
    seen = []
    def get(url):
        seen.append(parse_qs(urlparse(url).query).get("$where", [""])[0])
        return pages[len(seen) - 1]
    first = base.update(db, spec, raw_dir=tmp_path, get=get, log=lambda *_: None)
    assert first == {"loaded": 2, "skipped": 0, "without_coordinates": 0}
    assert db.get(LocalCrash, ("montgomery_md", "B")).road == "SENECA CREEK TRL+OTHER RD"
    base.update(db, spec, raw_dir=tmp_path, get=get, log=lambda *_: None)
    assert "2026-11-08" in seen[1]  # newest held minus 3-day overlap
    assert db.get(LocalCrash, ("montgomery_md", "B")).severity == "Fatal Crash"
    assert db.scalar(select(func.count()).select_from(LocalCrash)) == 2
