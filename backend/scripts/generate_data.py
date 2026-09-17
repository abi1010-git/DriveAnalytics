"""Create reproducible, simulated SafeDrive data. No real vehicle data is used."""
import random, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base, SessionLocal, engine
from app.models import Vehicle, Telemetry, SafetyEvent

random.seed(42); Base.metadata.drop_all(engine); Base.metadata.create_all(engine); db=SessionLocal()
versions=["sim-1.0","sim-1.1","sim-2.0"]; routes=[f"R-{i:02d}" for i in range(1,7)]
vehicles=[]
for i in range(20):
    v=Vehicle(vehicle_name=f"SD-{i+1:03d}", software_version=random.choice(versions), status=random.choice(["ACTIVE","MAINTENANCE","STANDBY"])); db.add(v); vehicles.append(v)
db.flush(); start=datetime(2026,1,1)
for v in vehicles:
    for j in range(250):
        ts=start+timedelta(minutes=j*10+v.id); speed=max(0,random.gauss(32,12)); accel=random.gauss(0,0.8); sensor="DEGRADED" if random.random()<.025 else "OK"
        db.add(Telemetry(vehicle_id=v.id,timestamp=ts,speed_mph=round(speed,2),acceleration_mps2=round(accel,2),steering_angle=round(random.gauss(0,8),2),brake_pressure=round(max(0,random.gauss(18,12)),2),battery_percent=round(100-j*.18-random.random()*3,2),sensor_status=sensor,route_id=random.choice(routes)))
db.flush(); rows=db.query(Telemetry).all()
for t in rows:
    kind=None
    if t.acceleration_mps2 < -2.2: kind="HARD_BRAKING"
    elif t.sensor_status != "OK": kind="SENSOR_FAILURE"
    elif t.speed_mph > 58: kind="SPEED_THRESHOLD"
    elif t.acceleration_mps2 > 2.2: kind="RAPID_ACCELERATION"
    elif random.random()<.018: kind="NEAR_COLLISION_SIMULATED"
    if kind:
        sev="CRITICAL" if kind in ("SENSOR_FAILURE","NEAR_COLLISION_SIMULATED") and random.random()<.25 else random.choice(["LOW","MEDIUM","HIGH"])
        db.add(SafetyEvent(vehicle_id=t.vehicle_id,timestamp=t.timestamp,event_type=kind,severity=sev,description=f"Simulated {kind.lower().replace('_',' ')} detected from telemetry.",software_version=vehicles[t.vehicle_id-1].software_version,route_id=t.route_id))
db.commit(); print(f"Created {len(vehicles)} vehicles, {len(rows)} telemetry records, {db.query(SafetyEvent).count()} events")
