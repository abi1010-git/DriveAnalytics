from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from ..models import Vehicle, Telemetry, SafetyEvent

def filtered_events(db: Session, **filters):
    stmt = select(SafetyEvent).order_by(SafetyEvent.timestamp.desc())
    for field in ("vehicle_id", "event_type", "severity", "software_version", "route_id"):
        if filters.get(field) not in (None, ""):
            stmt = stmt.where(getattr(SafetyEvent, field) == filters[field])
    if filters.get("start_date"): stmt = stmt.where(SafetyEvent.timestamp >= filters["start_date"])
    if filters.get("end_date"): stmt = stmt.where(SafetyEvent.timestamp <= filters["end_date"])
    return db.scalars(stmt).all()

def summary(db: Session):
    def counts(field):
        rows = db.execute(select(field, func.count()).group_by(field)).all()
        return {str(k): v for k, v in rows}
    return {"total_telemetry_records": db.scalar(select(func.count(Telemetry.id))) or 0,
            "total_safety_events": db.scalar(select(func.count(SafetyEvent.id))) or 0,
            "total_vehicles": db.scalar(select(func.count(Vehicle.id))) or 0,
            "events_by_severity": counts(SafetyEvent.severity), "events_by_event_type": counts(SafetyEvent.event_type),
            "events_by_software_version": counts(SafetyEvent.software_version), "events_per_vehicle": counts(SafetyEvent.vehicle_id),
            "hard_braking_count": db.scalar(select(func.count()).where(SafetyEvent.event_type == "HARD_BRAKING")) or 0,
            "sensor_failure_count": db.scalar(select(func.count()).where(SafetyEvent.event_type == "SENSOR_FAILURE")) or 0}

def nearby(db: Session, event: SafetyEvent):
    return db.scalars(select(Telemetry).where(Telemetry.vehicle_id == event.vehicle_id,
        Telemetry.timestamp.between(event.timestamp - timedelta(minutes=10), event.timestamp + timedelta(minutes=10)))
        .order_by(Telemetry.timestamp)).all()
