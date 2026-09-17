import os
from datetime import datetime
os.environ["DATABASE_URL"]="sqlite:///./test_safedrive.db"
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import Vehicle, SafetyEvent
Base.metadata.create_all(engine)
db=SessionLocal()
if not db.query(Vehicle).count():
    v=Vehicle(vehicle_name="TEST-001",software_version="sim-test",status="ACTIVE");db.add(v);db.flush();db.add(SafetyEvent(vehicle_id=v.id,timestamp=datetime(2026,1,1),event_type="HARD_BRAKING",severity="HIGH",description="test",software_version="sim-test",route_id="R-01"));db.commit()
client=TestClient(app)
def test_health(): assert client.get('/health').json()['synthetic_data'] is True
def test_event_filter():
    r=client.get('/api/events',params={'severity':'HIGH'}); assert r.status_code==200 and all(x['severity']=='HIGH' for x in r.json())
def test_summary(): assert client.get('/api/metrics/summary').json()['hard_braking_count']>=1
