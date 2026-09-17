from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import Vehicle, Telemetry, SafetyEvent, SparkVehicleSummary, SparkRouteSummary, SafetyEvaluation
from ..schemas.api import VehicleOut, TelemetryOut, EventOut, EventDetail, SparkVehicleSummaryOut, SparkRouteSummaryOut, SafetyEvaluationOut
from ..services.rule_engine import load_rules
from pathlib import Path
from ..services.queries import filtered_events, summary, nearby

router = APIRouter(prefix="/api")
@router.get("/safety/rules")
def safety_rules(): return load_rules(Path(__file__).resolve().parents[1] / "../config/safety_rules.yaml").model_dump()
@router.get("/safety/evaluations", response_model=list[SafetyEvaluationOut])
def safety_evaluations(vehicle_id: int|None=None, rule_id: str|None=None, severity: str|None=None, route_id: str|None=None, db: Session=Depends(get_db)):
    stmt=select(SafetyEvaluation).order_by(SafetyEvaluation.timestamp.desc())
    for field in ("vehicle_id","rule_id","severity","route_id"):
        value=locals()[field]
        if value not in (None,""): stmt=stmt.where(getattr(SafetyEvaluation,field)==value)
    return db.scalars(stmt).all()
@router.get("/safety/evaluations/{evaluation_id}", response_model=SafetyEvaluationOut)
def safety_evaluation(evaluation_id: int, db: Session=Depends(get_db)):
    evaluation=db.get(SafetyEvaluation,evaluation_id)
    if not evaluation: raise HTTPException(404,"Safety evaluation not found")
    return evaluation
@router.get("/analytics/fleet-summary", response_model=list[SparkVehicleSummaryOut])
def spark_fleet_summary(db: Session = Depends(get_db)): return db.scalars(select(SparkVehicleSummary).order_by(SparkVehicleSummary.vehicle_id)).all()
@router.get("/analytics/routes", response_model=list[SparkRouteSummaryOut])
def spark_routes(db: Session = Depends(get_db)): return db.scalars(select(SparkRouteSummary).order_by(SparkRouteSummary.route_id)).all()
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
