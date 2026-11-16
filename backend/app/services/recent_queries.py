"""Recent crash data from every source newer than FARS, merged for the map.

Three kinds of source, kept distinct in every response because they mean different things:
  record  filed police crash reports (NYC, Chicago): injury counts, days behind
  live    live incident feeds (Austin, CHP, ...): minutes behind, but unverified reports
FARS (fatal only, ~1.5 years behind) is served by map_queries.

Times: NYC and city records are in local time as published; live incidents are stored in
UTC. At the day/month granularity this API works at, the difference is not material.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Integer, Text, cast, func, literal, null, select
from sqlalchemy.orm import Session

from ..models import LiveIncident, LocalCrash, NycCrash

# Where each source has data. bbox = (min_lon, min_lat, max_lon, max_lat); states are FIPS.
SOURCES = {
    "nyc": {"kind": "record", "label": "New York City crash reports", "states": [36], "bbox": (-74.26, 40.49, -73.69, 40.92)},
    "chicago": {"kind": "record", "label": "Chicago crash reports", "states": [17], "bbox": (-87.95, 41.64, -87.52, 42.03)},
    "austin": {"kind": "live", "label": "Austin & Travis County incidents", "states": [48], "bbox": (-98.3, 29.9, -97.2, 30.75)},
    "chp": {"kind": "live", "label": "California Highway Patrol incidents", "states": [6], "bbox": (-124.5, 32.5, -114.1, 42.0)},
    "seattle": {"kind": "live", "label": "Seattle Fire 911 vehicle calls", "states": [53], "bbox": (-122.45, 47.48, -122.2, 47.74)},
    "sf": {"kind": "live", "label": "San Francisco police dispatch", "states": [6], "bbox": (-122.52, 37.70, -122.35, 37.84)},
    "wsdot": {"kind": "live", "label": "Washington state highway alerts", "states": [53], "bbox": (-124.8, 45.5, -116.9, 49.0)},
    "nj511": {"kind": "live", "label": "511NJ / TRANSCOM incidents", "states": [34, 36, 9, 42], "bbox": (-75.6, 38.9, -71.8, 41.4)},
}


@dataclass
class Window:
    start: datetime | None = None
    end: datetime | None = None
    bbox: tuple[float, float, float, float] | None = None


def _filters(window: Window, time_col, lat_col, lon_col):
    out = []
    if window.start:
        out.append(time_col >= window.start)
    if window.end:
        out.append(time_col < window.end)
    if window.bbox:
        min_lon, min_lat, max_lon, max_lat = window.bbox
        out += [lon_col.between(min_lon, max_lon), lat_col.between(min_lat, max_lat)]
    return out


def _overlaps(source: str, bbox) -> bool:
    if bbox is None:
        return True
    a, b = SOURCES[source]["bbox"], bbox
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _selects(window: Window, live_crashes_only: bool):
    """One SELECT per table, all with the same columns, so they can be counted or listed alike."""
    nyc = (select(literal("nyc").label("source"), NycCrash.collision_id.label("id"), NycCrash.crash_datetime.label("time"),
                  NycCrash.latitude.label("lat"), NycCrash.longitude.label("lon"), NycCrash.persons_killed.label("killed"),
                  NycCrash.persons_injured.label("injured"), func.coalesce(NycCrash.on_street, NycCrash.off_street).label("road"),
                  literal("crash").label("category"), cast(null(), Text).label("type"))
           .where(*_filters(window, NycCrash.crash_datetime, NycCrash.latitude, NycCrash.longitude)))
    local = (select(LocalCrash.source, LocalCrash.source_id.label("id"), LocalCrash.crash_datetime.label("time"), LocalCrash.latitude.label("lat"),
                    LocalCrash.longitude.label("lon"), LocalCrash.killed, LocalCrash.injured, LocalCrash.road,
                    literal("crash").label("category"), LocalCrash.crash_type.label("type"))
             .where(*_filters(window, LocalCrash.crash_datetime, LocalCrash.latitude, LocalCrash.longitude)))
    live = (select(LiveIncident.source, LiveIncident.source_id.label("id"), LiveIncident.reported_at.label("time"), LiveIncident.latitude.label("lat"),
                   LiveIncident.longitude.label("lon"), cast(null(), Integer).label("killed"), cast(null(), Integer).label("injured"), LiveIncident.road,
                   LiveIncident.category, LiveIncident.raw_type.label("type"))
            .where(*_filters(window, LiveIncident.reported_at, LiveIncident.latitude, LiveIncident.longitude)))
    if live_crashes_only:
        live = live.where(LiveIncident.category == "crash")
    return {"nyc": nyc, "local": local, "live": live}


def summary(db: Session, window: Window, live_crashes_only: bool = True) -> list[dict]:
    """Per source: crashes (or incidents) in the window, deaths and injuries where known, date range."""
    out = []
    for key, stmt in _selects(window, live_crashes_only).items():
        if key == "nyc" and not _overlaps("nyc", window.bbox):
            continue
        sub = stmt.subquery()
        rows = db.execute(select(sub.c.source, func.count(), func.sum(sub.c.killed), func.sum(sub.c.injured),
                                 func.min(sub.c.time), func.max(sub.c.time), func.count(sub.c.lat))
                          .group_by(sub.c.source)).all()
        for source, n, killed, injured, first, last, located in rows:
            meta = SOURCES.get(source, {"kind": "live" if key == "live" else "record", "label": source})
            out.append({"source": source, "kind": meta["kind"], "label": meta["label"], "count": n,
                        "killed": killed, "injured": injured, "first": first, "last": last, "with_coordinates": located})
    return sorted(out, key=lambda r: -r["count"])


def points(db: Session, window: Window, limit: int, live_crashes_only: bool = True) -> list[dict]:
    """Newest located crashes/incidents in the window across sources, at most `limit` per table."""
    out = []
    for key, stmt in _selects(window, live_crashes_only).items():
        if key == "nyc" and not _overlaps("nyc", window.bbox):
            continue
        sub = stmt.subquery()
        rows = db.execute(select(sub).where(sub.c.lat.is_not(None)).order_by(sub.c.time.desc()).limit(limit)).mappings().all()
        out += [{**row, "kind": SOURCES.get(row["source"], {}).get("kind", "live" if key == "live" else "record")} for row in rows]
    return sorted(out, key=lambda r: r["time"], reverse=True)


def monthly(db: Session, window: Window, live_crashes_only: bool = True) -> list[dict]:
    """Crash counts per month per source, for the trend chart."""
    postgres = db.get_bind().dialect.name == "postgresql"
    out = []
    for key, stmt in _selects(window, live_crashes_only).items():
        if key == "nyc" and not _overlaps("nyc", window.bbox):
            continue
        sub = stmt.subquery()
        month = func.to_char(sub.c.time, "YYYY-MM") if postgres else func.strftime("%Y-%m", sub.c.time)
        rows = db.execute(select(sub.c.source, month.label("month"), func.count()).group_by(sub.c.source, month).order_by(month)).all()
        out += [{"source": s, "month": m, "count": n} for s, m, n in rows]
    return out


def _register_record_specs() -> None:
    """Crash-record portals describe their own coverage in pipeline/records/sources."""
    from pipeline.records import all_specs
    for spec in all_specs().values():
        SOURCES.setdefault(spec.source, {"kind": "record", "label": spec.label, "states": spec.states, "bbox": spec.bbox})


_register_record_specs()


def coverage() -> list[dict]:
    return [{"source": key, **{k: v for k, v in meta.items()}} for key, meta in SOURCES.items()]
