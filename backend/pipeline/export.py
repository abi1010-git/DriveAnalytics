"""Export the database to static JSON files for the serverless site (docs/STATIC_SITE.md).

    python -m pipeline export --out ../frontend/public/data

The browser does the filtering and summing, so the files hold small building blocks:
- FARS: every crash, one file per state.
- Recent sources: counts on a 0.05° grid per year, and dots for the last 12 months in 1° tiles.
- Live: the last 24 hours.
Rows are arrays rather than objects to keep the files small.
"""
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Integer, Text, cast, extract, func, literal, select
from sqlalchemy.orm import Session

from app.models import CrashFlag, FarsCrash, LiveIncident, LocalCrash, NycCrash
from app.services import recent_queries
from app.services.rule_engine import load_rules

GRID_DEG = 0.05
TILE_DEG = 1
TILE_CAP = 5000  # newest dots per source per tile (2000 left Manhattan with ~700 dots vs the API's 3000)
DOT_DAYS = 365


def _write(path: Path, data) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, separators=(",", ":"), default=_json_default)
    path.write_text(text, encoding="utf-8")
    return len(text)


def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _round(value: float | None, places: int = 5) -> float | None:
    return None if value is None else round(value, places)


def _floor(db: Session, column):
    """floor() that works on PostgreSQL and SQLite (where CAST truncates toward zero)."""
    if db.get_bind().dialect.name == "postgresql":
        return cast(func.floor(column), Integer)
    offset = 1_000_000  # keeps the value positive so truncation equals floor
    return cast(column + offset, Integer) - offset


def _tables(live_crashes_only: bool = True):
    """(time, lat, lon, killed, injured, source, id, road, category, type, extra filters) per table,
    the same columns recent_queries uses."""
    nyc = dict(time=NycCrash.crash_datetime, lat=NycCrash.latitude, lon=NycCrash.longitude, killed=NycCrash.persons_killed,
               injured=NycCrash.persons_injured, source=None, id=NycCrash.collision_id,
               road=func.coalesce(NycCrash.on_street, NycCrash.off_street), category=None, type=None, where=[])
    local = dict(time=LocalCrash.crash_datetime, lat=LocalCrash.latitude, lon=LocalCrash.longitude, killed=LocalCrash.killed,
                 injured=LocalCrash.injured, source=LocalCrash.source, id=LocalCrash.source_id, road=LocalCrash.road,
                 category=None, type=LocalCrash.crash_type, where=[])
    live = dict(time=LiveIncident.reported_at, lat=LiveIncident.latitude, lon=LiveIncident.longitude, killed=None, injured=None,
                source=LiveIncident.source, id=LiveIncident.source_id, road=LiveIncident.road, category=LiveIncident.category,
                type=LiveIncident.raw_type, where=[LiveIncident.category == "crash"] if live_crashes_only else [])
    return {"nyc": nyc, "local": local, "live": live}


def _source_col(t: dict, name: str):
    return t["source"] if t["source"] is not None else literal(name)


def _keys(t: dict) -> list:
    """GROUP BY keys for the source column; PostgreSQL rejects grouping by a constant (NYC's)."""
    return [t["source"]] if t["source"] is not None else []


def _sum(column):
    return func.sum(column) if column is not None else cast(None, Integer)


def export_fars(db: Session, out: Path) -> dict:
    states = db.execute(select(FarsCrash.state_code, func.max(FarsCrash.state_name), FarsCrash.year, func.count(),
                               func.coalesce(func.sum(FarsCrash.fatalities), 0))
                        .group_by(FarsCrash.state_code, FarsCrash.year).order_by(FarsCrash.state_code, FarsCrash.year)).all()
    _write(out / "fars" / "states.json", [list(row) for row in states])
    flags: dict[str, list[str]] = defaultdict(list)
    for crash_id, flag_id in db.execute(select(CrashFlag.crash_id, CrashFlag.flag_id).where(CrashFlag.source == "fars")
                                        .order_by(CrashFlag.crash_id, CrashFlag.flag_id)):
        flags[crash_id].append(flag_id)
    years = sorted({row[2] for row in states})
    for state_code in sorted({row[0] for row in states}):
        crashes = db.scalars(select(FarsCrash).where(FarsCrash.state_code == state_code).order_by(FarsCrash.crash_date.desc(), FarsCrash.id)).all()
        counties: dict[int, str] = {}
        for c in crashes:
            if c.county_code is not None and c.county_name and c.county_name > counties.get(c.county_code, ""):
                counties[c.county_code] = c.county_name  # the API shows max(county_name)
        rows = [[c.id, c.year, c.county_code, _round(c.latitude), _round(c.longitude), c.crash_date, c.hour, c.fatalities,
                 c.road_name, c.road_route, c.city_name, c.light_condition, c.weather, c.first_harmful_event, flags.get(c.id, []),
                 int(bool(c.speeding_involved)), int(bool(c.drinking_driver_involved)), int((c.pedestrians or 0) > 0)] for c in crashes]
        _write(out / "fars" / f"{state_code:02d}.json", {"counties": {str(k): v for k, v in sorted(counties.items())}, "crashes": rows})
    return {"fars_years": years, "fars_crashes": sum(row[3] for row in states)}


def export_recent(db: Session, out: Path) -> dict:
    """Per-year totals and grid counts for every source, all years."""
    totals, grid = [], defaultdict(lambda: defaultdict(lambda: [0, None, None]))
    for name, t in _tables().items():
        source, year = _source_col(t, name), cast(extract("year", t["time"]), Integer)
        stmt = select(source.label("s"), year.label("y"), func.count(), _sum(t["killed"]).label("k"), _sum(t["injured"]).label("i"),
                      func.min(t["time"]), func.max(t["time"])) \
            .where(t["time"].is_not(None), *t["where"]).group_by(*_keys(t), year)
        totals += [list(row) for row in db.execute(stmt)]
        gx, gy = _floor(db, t["lon"] / GRID_DEG), _floor(db, t["lat"] / GRID_DEG)
        stmt = select(source.label("s"), year.label("y"), gx.label("gx"), gy.label("gy"), func.count(),
                      _sum(t["killed"]).label("k"), _sum(t["injured"]).label("i")) \
            .where(t["time"].is_not(None), t["lat"].is_not(None), t["lon"].is_not(None), *t["where"]).group_by(*_keys(t), year, gx, gy)
        for src, yr, x, y, n, killed, injured in db.execute(stmt):
            grid[yr][(src, x, y)] = [n, killed, injured]
    _write(out / "recent" / "totals.json", sorted(totals, key=lambda r: (r[0], r[1])))
    years = sorted(grid)
    for yr in years:
        cells = grid[yr]
        sources = sorted({key[0] for key in cells})
        index = {s: i for i, s in enumerate(sources)}
        rows = [[index[s], x, y, n, k, i] for (s, x, y), (n, k, i) in sorted(cells.items())]
        _write(out / "recent" / f"grid-{yr}.json", {"sources": sources, "cells": rows})
    return {"recent_years": years, "grid_cells": sum(len(c) for c in grid.values())}


def export_tiles(db: Session, out: Path, since: datetime) -> dict:
    """Newest dots per source per 1° tile since `since`; at most TILE_CAP per source per tile."""
    tiles: dict[tuple[int, int], list] = defaultdict(list)
    kept: dict[tuple, int] = defaultdict(int)
    for name, t in _tables().items():
        cols = [_source_col(t, name), cast(t["id"], Text), t["time"], t["lat"], t["lon"],
                t["killed"] if t["killed"] is not None else cast(None, Integer),
                t["injured"] if t["injured"] is not None else cast(None, Integer),
                t["road"], t["category"] if t["category"] is not None else literal("crash"),
                t["type"] if t["type"] is not None else cast(None, Text)]
        stmt = select(*(col.label(f"c{i}") for i, col in enumerate(cols))).where(t["time"] >= since, t["lat"].is_not(None), t["lon"].is_not(None), *t["where"]) \
            .order_by(t["time"].desc()).execution_options(yield_per=20_000)
        for src, row_id, time, lat, lon, killed, injured, road, category, kind in db.execute(stmt):
            tile = (math.floor(lon / TILE_DEG), math.floor(lat / TILE_DEG))
            if kept[(src, tile)] >= TILE_CAP:
                continue
            kept[(src, tile)] += 1
            tiles[tile].append([src, str(row_id), time, _round(lat), _round(lon), killed, injured, road, category, kind])
    shutil.rmtree(out / "recent" / "tiles", ignore_errors=True)
    for (x, y), rows in tiles.items():
        rows.sort(key=lambda r: r[2], reverse=True)
        _write(out / "recent" / "tiles" / f"{x}_{y}.json", rows)
    return {"tiles": sorted(f"{x}_{y}" for x, y in tiles), "dots": sum(len(r) for r in tiles.values())}


def export_live(db: Session, out: Path, now: datetime) -> dict:
    """Everything in the 24 hours before the export, all incident categories, in the API's own shapes."""
    window = recent_queries.Window(start=now - timedelta(hours=24))
    summary = recent_queries.summary(db, window, live_crashes_only=False)
    points = recent_queries.points(db, window, limit=50_000, live_crashes_only=False)
    _write(out / "live" / "last24h.json", {"summary": summary, "points": points})
    return {"live_points": len(points)}


def run(db: Session, out: Path, now: datetime | None = None) -> dict:
    """Write every file; `now` (naive UTC) is the export time."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    out.mkdir(parents=True, exist_ok=True)
    since = now - timedelta(days=DOT_DAYS)
    _write(out / "flags.json", [rule.model_dump() for rule in load_rules().rules])
    _write(out / "coverage.json", recent_queries.coverage())
    meta = {"generated_at": now.isoformat() + "Z", "dot_days": DOT_DAYS, "dots_since": since.isoformat(),
            "grid_deg": GRID_DEG, "tile_deg": TILE_DEG, "tile_cap": TILE_CAP}
    meta.update(export_fars(db, out))
    meta.update(export_recent(db, out))
    meta.update(export_live(db, out, now))
    meta.update(export_tiles(db, out, since))
    _write(out / "meta.json", meta)
    return meta
