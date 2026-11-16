"""Crash data newer than FARS: city crash reports (NYC, Chicago) and live incident feeds."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import recent_queries as q

router = APIRouter(prefix="/api/recent", tags=["recent"])


def window(start: datetime | None = Query(None, description="date or datetime"), end: datetime | None = Query(None, description="exclusive"),
           bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat")) -> q.Window:
    box = None
    if bbox:
        try:
            box = tuple(float(v) for v in bbox.split(","))
            assert len(box) == 4 and box[0] <= box[2] and box[1] <= box[3]
        except (ValueError, AssertionError):
            raise HTTPException(422, "bbox must be min_lon,min_lat,max_lon,max_lat")
    naive = lambda d: d.replace(tzinfo=None) if d and d.tzinfo is None else (d.astimezone(timezone.utc).replace(tzinfo=None) if d else None)  # noqa: E731
    return q.Window(start=naive(start), end=naive(end), bbox=box)


@router.get("/coverage")
def coverage():
    """Which places each recent source covers (bbox and FIPS state codes) and what kind of data it is."""
    return q.coverage()


@router.get("/summary")
def summary(w: q.Window = Depends(window), all_incidents: bool = False, db: Session = Depends(get_db)):
    """Counts per source in the window. Live feeds count crashes only unless all_incidents=true."""
    return q.summary(db, w, live_crashes_only=not all_incidents)


@router.get("/points")
def points(w: q.Window = Depends(window), limit: int = Query(3000, ge=1, le=10000), all_incidents: bool = False,
           db: Session = Depends(get_db)):
    """Newest located crashes/incidents in the window, up to `limit` per table. Needs a bbox."""
    if w.bbox is None:
        raise HTTPException(422, "points needs a bbox")
    return q.points(db, w, limit, live_crashes_only=not all_incidents)


@router.get("/monthly")
def monthly(w: q.Window = Depends(window), db: Session = Depends(get_db)):
    """Crashes per month per source in the window."""
    return q.monthly(db, w)
