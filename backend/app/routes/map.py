"""Endpoints behind the map drill-down (US -> state -> county/city -> roads and crashes)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import map_queries as q

router = APIRouter(prefix="/api/map", tags=["map"])


def area(state_code: int | None = None, county_code: int | None = None, city: str | None = None,
         year_from: int | None = None, year_to: int | None = None) -> q.Area:
    return q.Area(state_code=state_code, county_code=county_code, city_name=city or None, year_from=year_from, year_to=year_to)


@router.get("/states")
def states(a: q.Area = Depends(area), db: Session = Depends(get_db)):
    """Fatal crashes and deaths per state (state_code is the FIPS code)."""
    return q.states(db, a)


@router.get("/counties")
def counties(state_code: int, a: q.Area = Depends(area), db: Session = Depends(get_db)):
    """Fatal crashes and deaths per county in one state; `fips` matches US county boundary IDs."""
    return q.counties(db, a)


@router.get("/cities")
def cities(state_code: int, a: q.Area = Depends(area), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db)):
    """Cities with the most deaths in a state (or county). Crashes outside city limits have no city."""
    return q.cities(db, a, limit)


@router.get("/summary")
def summary(a: q.Area = Depends(area), road_limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Everything the side panel needs for one area: top roads, flags and crashes by hour."""
    return {"roads": q.roads(db, a, road_limit), "factors": q.flag_breakdown(db, a), "hours": q.hours(db, a)}


@router.get("/crashes")
def crashes(state_code: int, a: q.Area = Depends(area), limit: int = Query(3000, ge=1, le=10000), db: Session = Depends(get_db)):
    """Crash points with coordinates for the map, newest first."""
    return q.crash_points(db, a, limit)
