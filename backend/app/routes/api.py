from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import Vehicle, Telemetry, SafetyEvent
from ..schemas.api import VehicleOut, TelemetryOut, EventOut, EventDetail
from ..services.queries import filtered_events, summary, nearby

router = APIRouter(prefix="/api")
@router.get("/vehicles", response_model=list[VehicleOut])
def vehicles(db: Session = Depends(get_db)): return db.scalars(select(Vehicle).order_by(Vehicle.id)).all()
@router.get("/events", response_model=list[EventOut])
def events(vehicle_id: int|None=None, event_type: str|None=None, severity: str|None=None, software_version: str|None=None, route_id: str|None=None, start_date: datetime|None=None, end_date: datetime|None=None, db: Session=Depends(get_db)):
    return filtered_events(db, vehicle_id=vehicle_id, event_type=event_type, severity=severity, software_version=software_version, route_id=route_id, start_date=start_date, end_date=end_date)
@router.get("/events/{event_id}", response_model=EventDetail)
def event_detail(event_id: int, db: Session=Depends(get_db)):
    event = db.scalar(select(SafetyEvent).options(joinedload(SafetyEvent.vehicle)).where(SafetyEvent.id == event_id))
    if not event: raise HTTPException(404, "Safety event not found")
    return {**event.__dict__, "vehicle": event.vehicle, "nearby_telemetry": nearby(db, event)}
@router.get("/metrics/summary")
def metrics(db: Session=Depends(get_db)): return summary(db)
@router.get("/vehicles/{vehicle_id}/telemetry", response_model=list[TelemetryOut])
def telemetry(vehicle_id: int, start_date: datetime|None=None, end_date: datetime|None=None, db: Session=Depends(get_db)):
    if not db.get(Vehicle, vehicle_id): raise HTTPException(404, "Vehicle not found")
    stmt=select(Telemetry).where(Telemetry.vehicle_id==vehicle_id).order_by(Telemetry.timestamp)
    if start_date: stmt=stmt.where(Telemetry.timestamp>=start_date)
    if end_date: stmt=stmt.where(Telemetry.timestamp<=end_date)
    return db.scalars(stmt).all()
