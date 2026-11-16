"""Live traffic incidents from city and state feeds, and how fresh each feed is."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import LiveIncident, LivePoll

router = APIRouter(prefix="/api/live", tags=["live"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    """Each live source with its last poll, last successful poll, newest incident and 24-hour counts."""
    from pipeline.live import ADAPTERS  # the adapters own each source's label

    now = _now()
    out = []
    for name, adapter in ADAPTERS.items():
        last = db.scalar(select(LivePoll).where(LivePoll.source == name).order_by(LivePoll.polled_at.desc()).limit(1))
        last_ok = db.scalar(select(func.max(LivePoll.polled_at)).where(LivePoll.source == name, LivePoll.error.is_(None)))
        newest, total_24h, crashes_24h = db.execute(select(
            func.max(LiveIncident.reported_at),
            func.count().filter(LiveIncident.reported_at >= now - timedelta(hours=24)),
            func.count().filter((LiveIncident.reported_at >= now - timedelta(hours=24)) & (LiveIncident.category == "crash")),
        ).where(LiveIncident.source == name)).one()
        out.append({"source": name, "label": adapter.LABEL, "last_poll_at": last.polled_at if last else None,
                    "last_error": last.error if last else None, "last_success_at": last_ok, "newest_incident_at": newest,
                    "incidents_24h": total_24h, "crashes_24h": crashes_24h})
    return out


@router.get("/incidents")
def incidents(hours: float = Query(6, gt=0, le=24 * 365), category: str | None = None, source: str | None = None,
              active_only: bool = False, bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
              limit: int = Query(2000, ge=1, le=10000), db: Session = Depends(get_db)):
    """Incidents reported in the last `hours`, newest first. Times are UTC."""
    stmt = (select(LiveIncident).where(LiveIncident.reported_at >= _now() - timedelta(hours=hours))
            .order_by(LiveIncident.reported_at.desc()).limit(limit))
    if category:
        stmt = stmt.where(LiveIncident.category == category)
    if source:
        stmt = stmt.where(LiveIncident.source == source)
    if active_only:
        stmt = stmt.where(LiveIncident.status == "active")
    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox.split(","))
        except ValueError:
            raise HTTPException(422, "bbox must be min_lon,min_lat,max_lon,max_lat")
        stmt = stmt.where(LiveIncident.longitude.between(min_lon, max_lon), LiveIncident.latitude.between(min_lat, max_lat))
    return [{"source": r.source, "id": r.source_id, "category": r.category, "type": r.raw_type, "road": r.road,
             "description": r.description, "latitude": r.latitude, "longitude": r.longitude, "reported_at": r.reported_at,
             "updated_at": r.updated_at, "status": r.status, "cleared_at": r.cleared_at} for r in db.scalars(stmt)]
