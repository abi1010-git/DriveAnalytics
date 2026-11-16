import json
from datetime import datetime

import pytest

from app.models import LocalCrash
from pipeline import export, fars, nyc
from pipeline.live import austin
from pipeline.live.poller import poll_source
from tests.conftest import accident, nyc_row, vehicle
from tests.test_live import austin_row

NOW = datetime(2026, 11, 16, 12)


@pytest.fixture
def out(db, rules, fars_zip, nyc_file, tmp_path):
    crashes = [
        accident(ST_CASE="10001", CITY="5", CITYNAME="TUSCALOOSA", TWAY_ID="I-20", FATALS="2"),
        accident(ST_CASE="10002", CITY="5", CITYNAME="TUSCALOOSA", TWAY_ID="I-20", PEDS="1"),
        accident(STATE="6", STATENAME="California", ST_CASE="60001", COUNTY="37", COUNTYNAME="LOS ANGELES (37)", TWAY_ID="I-5"),
    ]
    fars.load_year(db, fars_zip(crashes, [vehicle(10001, SPEEDREL="3")]), 2024, rules.for_source("fars"))
    nyc.load_file(db, nyc_file([nyc_row("n1"), nyc_row("n2", crash_date="2019-03-02T00:00:00.000", number_of_persons_killed="1"),
                                nyc_row("n3", latitude=None, longitude=None)]), rules.for_source("nyc"), log=lambda *_: None)
    db.add_all([LocalCrash(source="chicago", source_id=f"c{i}", crash_datetime=datetime(2026, 11, 14, 8, i), latitude=41.88, longitude=-87.63,
                           road="W MADISON ST", injured=2, killed=0) for i in range(3)])
    db.commit()
    poll_source(db, austin, now=datetime(2026, 11, 16, 6), get=lambda url: json.dumps([austin_row("a1"), austin_row("a2", issue="Traffic Hazard")]))
    path = tmp_path / "data"
    export.run(db, path, now=NOW)
    return path


def read(path, name):
    return json.loads((path / name).read_text(encoding="utf-8"))


def test_meta(out):
    meta = read(out, "meta.json")
    assert meta["generated_at"] == "2026-11-16T12:00:00Z" and meta["fars_years"] == [2024]
    assert meta["recent_years"] == [2019, 2026] and "-88_41" in meta["tiles"]


def test_fars_states_and_state_file(out):
    assert read(out, "fars/states.json") == [[1, "Alabama", 2024, 2, 3], [6, "California", 2024, 1, 1]]
    alabama = read(out, "fars/01.json")
    assert alabama["counties"] == {"125": "TUSCALOOSA"}
    first = {row[0]: row for row in alabama["crashes"]}["2024-10001"]
    assert first[1:3] == [2024, 125] and first[7] == 2 and first[9] == "I-20" and first[15:] == [1, 0, 0]
    assert "speeding" in " ".join(first[14])  # the speeding flag id travels with the crash
    assert {row[0]: row for row in alabama["crashes"]}["2024-10002"][17] == 1  # pedestrian


def test_recent_totals_and_grid(out):
    totals = {(r[0], r[1]): r for r in read(out, "recent/totals.json")}
    assert totals[("nyc", 2026)][2] == 2 and totals[("nyc", 2019)][3] == 1  # the unlocated crash counts in totals
    assert totals[("chicago", 2026)][2:5] == [3, 0, 6]
    assert totals[("austin", 2026)][2] == 1  # only the crash, not the hazard
    grid = read(out, "recent/grid-2026.json")
    cells = {grid["sources"][c[0]]: c for c in grid["cells"]}
    assert cells["chicago"][1:] == [-1753, 837, 3, 0, 6]  # floor(-87.63/0.05), floor(41.88/0.05)
    assert cells["nyc"][3] == 1  # only the located 2026 crash


def test_tiles_cover_last_year_only(out):
    rows = read(out, "recent/tiles/-88_41.json")
    assert [r[0] for r in rows] == ["chicago"] * 3 and rows[0][2] >= rows[-1][2]
    nyc_rows = read(out, "recent/tiles/-74_40.json")
    assert [r[1] for r in nyc_rows] == ["n1"]  # n2 is from 2019, outside the dot window


def test_tile_cap(db, tmp_path, monkeypatch):
    monkeypatch.setattr(export, "TILE_CAP", 2)
    db.add_all([LocalCrash(source="chicago", source_id=f"c{i}", crash_datetime=datetime(2026, 11, 1, 8, i), latitude=41.88, longitude=-87.63)
                for i in range(5)])
    db.commit()
    export.run(db, tmp_path, now=NOW)
    assert [r[1] for r in read(tmp_path, "recent/tiles/-88_41.json")] == ["c4", "c3"]


def test_live_last24h(out):
    live = read(out, "live/last24h.json")
    assert {r["source"] for r in live["points"]} >= {"austin"}
    assert {r["source"]: r["count"] for r in live["summary"]}["austin"] == 2  # all incident categories
