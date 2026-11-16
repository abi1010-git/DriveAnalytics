"""Phase 1 API: what data is loaded, the risk flags, and simple crash listings.
Spatial search ("crashes near here"), severity rankings and trends come in Phase 2."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CrashFlag, FarsCrash, NycCrash, NycCrashFactor
from ..schemas.api import FarsCrashOut, NycCrashOut
from ..services.queries import dataset_summary, flag_counts, flags_for
from ..services.rule_engine import load_rules

router = APIRouter(prefix="/api")


def _bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """Parse "min_lon,min_lat,max_lon,max_lat" (the usual map-library order)."""
    if not bbox:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "bbox must be min_lon,min_lat,max_lon,max_lat")
    if min_lon > max_lon or min_lat > max_lat:
        raise HTTPException(422, "bbox minimums must be below maximums")
    return min_lon, min_lat, max_lon, max_lat


@router.get("/datasets")
def datasets(db: Session = Depends(get_db)):
    return dataset_summary(db)


@router.get("/risk-flags")
def risk_flags(db: Session = Depends(get_db)):
    return flag_counts(db, load_rules())


@router.get("/fars/crashes", response_model=list[FarsCrashOut])
def fars_crashes(year: int | None = None, state_code: int | None = None, flag: str | None = None,
                 bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
                 limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    stmt = select(FarsCrash).order_by(FarsCrash.crash_date.desc(), FarsCrash.id).limit(limit)
    if year is not None:
        stmt = stmt.where(FarsCrash.year == year)
    if state_code is not None:
        stmt = stmt.where(FarsCrash.state_code == state_code)
    if flag:
        stmt = stmt.join(CrashFlag, (CrashFlag.crash_id == FarsCrash.id) & (CrashFlag.source == "fars")).where(CrashFlag.flag_id == flag)
    if box := _bbox(bbox):
        stmt = stmt.where(FarsCrash.longitude.between(box[0], box[2]), FarsCrash.latitude.between(box[1], box[3]))
    crashes = db.scalars(stmt).all()
    flags = flags_for(db, "fars", [c.id for c in crashes])
    return [{**FarsCrashOut.model_validate(c).model_dump(), "flags": flags[c.id]} for c in crashes]


@router.get("/nyc/crashes", response_model=list[NycCrashOut])
def nyc_crashes(borough: str | None = None, start: date | None = None, end: date | None = None, flag: str | None = None,
                bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
                limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    stmt = select(NycCrash).order_by(NycCrash.crash_datetime.desc(), NycCrash.collision_id).limit(limit)
    if borough:
        stmt = stmt.where(NycCrash.borough == borough.upper())
    if start:
        stmt = stmt.where(NycCrash.crash_datetime >= start)
    if end:
        stmt = stmt.where(NycCrash.crash_datetime < end)
    if flag:
        stmt = stmt.join(CrashFlag, (CrashFlag.crash_id == NycCrash.collision_id) & (CrashFlag.source == "nyc")).where(CrashFlag.flag_id == flag)
    if box := _bbox(bbox):
        stmt = stmt.where(NycCrash.longitude.between(box[0], box[2]), NycCrash.latitude.between(box[1], box[3]))
    crashes = db.scalars(stmt).all()
    ids = [c.collision_id for c in crashes]
    flags = flags_for(db, "nyc", ids)
    factors: dict[str, list[str]] = {cid: [] for cid in ids}
    if ids:
        for cid, factor in db.execute(select(NycCrashFactor.collision_id, NycCrashFactor.factor)
                                      .where(NycCrashFactor.collision_id.in_(ids)).order_by(NycCrashFactor.vehicle_number)):
            factors[cid].append(factor)
    return [{**NycCrashOut.model_validate(c).model_dump(), "flags": flags[c.collision_id], "contributing_factors": factors[c.collision_id]}
            for c in crashes]
