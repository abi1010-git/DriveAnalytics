"""Aggregations behind the map drill-down: US -> state -> county or city -> roads and crashes.

All levels use FARS (fatal crashes). State and county codes are FIPS codes, which is what
the US map boundaries use too, so the frontend can join on them directly.
"""
from dataclasses import dataclass

from sqlalchemy import Select, case, desc, func, select
from sqlalchemy.orm import Session

from ..models import CrashFlag, FarsCrash


@dataclass
class Area:
    state_code: int | None = None
    county_code: int | None = None
    city_name: str | None = None
    year_from: int | None = None
    year_to: int | None = None

    def apply(self, stmt: Select) -> Select:
        if self.state_code is not None:
            stmt = stmt.where(FarsCrash.state_code == self.state_code)
        if self.county_code is not None:
            stmt = stmt.where(FarsCrash.county_code == self.county_code)
        if self.city_name:
            stmt = stmt.where(FarsCrash.city_name == self.city_name)
        if self.year_from is not None:
            stmt = stmt.where(FarsCrash.year >= self.year_from)
        if self.year_to is not None:
            stmt = stmt.where(FarsCrash.year <= self.year_to)
        return stmt


def _count_if(condition):
    return func.sum(case((condition, 1), else_=0))


_crashes = func.count().label("crashes")
_deaths = func.coalesce(func.sum(FarsCrash.fatalities), 0).label("deaths")


def states(db: Session, area: Area) -> list[dict]:
    stmt = area.apply(select(FarsCrash.state_code, func.max(FarsCrash.state_name).label("name"), _crashes, _deaths)
                      .group_by(FarsCrash.state_code).order_by(desc("deaths")))
    return [{"state_code": s, "name": n, "crashes": c, "deaths": d} for s, n, c, d in db.execute(stmt)]


def counties(db: Session, area: Area) -> list[dict]:
    stmt = area.apply(select(FarsCrash.county_code, func.max(FarsCrash.county_name).label("name"), _crashes, _deaths)
                      .where(FarsCrash.county_code.is_not(None)).group_by(FarsCrash.county_code).order_by(desc("deaths")))
    return [{"county_code": code, "fips": f"{area.state_code:02d}{code:03d}", "name": n, "crashes": c, "deaths": d}
            for code, n, c, d in db.execute(stmt)]


def cities(db: Session, area: Area, limit: int) -> list[dict]:
    stmt = area.apply(select(FarsCrash.city_name, func.max(FarsCrash.county_code).label("county_code"), _crashes, _deaths,
                             func.avg(FarsCrash.latitude).label("lat"), func.avg(FarsCrash.longitude).label("lon"))
                      .where(FarsCrash.city_name.is_not(None)).group_by(FarsCrash.city_name).order_by(desc("deaths"), desc("crashes")).limit(limit))
    return [{"name": n, "county_code": cc, "crashes": c, "deaths": d, "latitude": lat, "longitude": lon}
            for n, cc, c, d, lat, lon in db.execute(stmt)]


def roads(db: Session, area: Area, limit: int) -> list[dict]:
    """Roads ranked by deaths, then by crash count, grouped by the normalized route key so
    "I-45", "I-45/NORTH FWY" and "I-45/GULF FWY" count as one road. `name` is the most
    common way the road was written in this area, for display."""
    stmt = area.apply(select(FarsCrash.road_route, _crashes, _deaths,
                             _count_if(FarsCrash.speeding_involved.is_(True)).label("speeding"),
                             _count_if(FarsCrash.drinking_driver_involved.is_(True)).label("drinking"),
                             _count_if(FarsCrash.pedestrians > 0).label("non_motorist"))
                      .where(FarsCrash.road_route.is_not(None)).group_by(FarsCrash.road_route)
                      .order_by(desc("deaths"), desc("crashes"), FarsCrash.road_route).limit(limit))
    rows = db.execute(stmt).all()
    names: dict[str, tuple[int, str]] = {}
    if rows:
        variants = area.apply(select(FarsCrash.road_route, FarsCrash.road_name, func.count())
                              .where(FarsCrash.road_route.in_([r[0] for r in rows])).group_by(FarsCrash.road_route, FarsCrash.road_name))
        for route, name, count in db.execute(variants):
            if route not in names or (count, name) > names[route]:
                names[route] = (count, name)
    return [{"road_route": r, "name": names.get(r, (0, r))[1], "crashes": c, "deaths": d,
             "speeding_crashes": s or 0, "drinking_crashes": dr or 0, "non_motorist_crashes": nm or 0}
            for r, c, d, s, dr, nm in rows]


def flag_breakdown(db: Session, area: Area) -> dict:
    total, deaths = db.execute(area.apply(select(func.count(), func.coalesce(func.sum(FarsCrash.fatalities), 0)).select_from(FarsCrash))).one()
    stmt = area.apply(select(CrashFlag.flag_id, func.count()).join(FarsCrash, (CrashFlag.crash_id == FarsCrash.id) & (CrashFlag.source == "fars"))
                      .group_by(CrashFlag.flag_id).order_by(desc(func.count())))
    return {"total_crashes": total, "total_deaths": deaths, "flags": [{"flag_id": f, "crashes": n} for f, n in db.execute(stmt)]}


def hours(db: Session, area: Area) -> list[dict]:
    stmt = area.apply(select(FarsCrash.hour, _crashes).where(FarsCrash.hour.is_not(None)).group_by(FarsCrash.hour).order_by(FarsCrash.hour))
    counts = dict(db.execute(stmt).all())
    return [{"hour": h, "crashes": counts.get(h, 0)} for h in range(24)]


def crash_points(db: Session, area: Area, limit: int) -> list[dict]:
    stmt = area.apply(select(FarsCrash).where(FarsCrash.latitude.is_not(None))
                      .order_by(FarsCrash.crash_date.desc(), FarsCrash.id).limit(limit))
    rows = db.scalars(stmt).all()
    flags: dict[str, list[str]] = {r.id: [] for r in rows}
    if rows:
        for cid, flag in db.execute(select(CrashFlag.crash_id, CrashFlag.flag_id).where(CrashFlag.source == "fars", CrashFlag.crash_id.in_(list(flags)))):
            flags[cid].append(flag)
    return [{"id": r.id, "latitude": r.latitude, "longitude": r.longitude, "date": r.crash_date, "hour": r.hour, "deaths": r.fatalities,
             "road_name": r.road_name, "road_route": r.road_route, "city_name": r.city_name, "light_condition": r.light_condition, "weather": r.weather,
             "first_harmful_event": r.first_harmful_event, "flags": flags[r.id]} for r in rows]
