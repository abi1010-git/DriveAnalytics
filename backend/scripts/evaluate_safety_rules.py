"""Evaluate triggered YAML safety rules against database telemetry."""
import argparse, json, sys
from pathlib import Path
from sqlalchemy import delete, select
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base, SessionLocal, engine
from app.models import SafetyEvaluation, Telemetry, Vehicle
from app.services.rule_engine import load_rules, evaluate_record

def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',type=Path,default=Path('config/safety_rules.yaml')); p.add_argument('--max-records',type=int); p.add_argument('--vehicle-id',type=int); p.add_argument('--start-date'); p.add_argument('--end-date'); args=p.parse_args()
    rules=load_rules(args.config); db=SessionLocal(); Base.metadata.create_all(engine)
    stmt=select(Telemetry,Vehicle.software_version).join(Vehicle).order_by(Telemetry.timestamp,Telemetry.id)
    if args.vehicle_id: stmt=stmt.where(Telemetry.vehicle_id==args.vehicle_id)
    if args.start_date: stmt=stmt.where(Telemetry.timestamp>=args.start_date)
    if args.end_date: stmt=stmt.where(Telemetry.timestamp<=args.end_date)
    if args.max_records: stmt=stmt.limit(args.max_records)
    count=0; evaluations=[]
    try:
        for telemetry,version in db.execute(stmt).yield_per(5000):
            count += 1
            record={"vehicle_id":telemetry.vehicle_id,"timestamp":telemetry.timestamp,"speed_mph":telemetry.speed_mph,"acceleration_mps2":telemetry.acceleration_mps2,"steering_angle":telemetry.steering_angle,"brake_pressure":telemetry.brake_pressure,"battery_percent":telemetry.battery_percent,"sensor_status":telemetry.sensor_status,"route_id":telemetry.route_id,"software_version":version}
            for result in evaluate_record(record,rules): evaluations.append({"telemetry_id":telemetry.id,"vehicle_id":telemetry.vehicle_id,"timestamp":telemetry.timestamp,"rule_id":result["rule_id"],"rule_name":result["rule_name"],"severity":result["severity"],"evidence":result["evidence"],"software_version":version,"route_id":telemetry.route_id})
        db.execute(delete(SafetyEvaluation))
        if evaluations: db.add_all([SafetyEvaluation(**row) for row in evaluations])
        db.commit()
    finally: db.close()
    counts={}
    for row in evaluations: counts[row['rule_id']]=counts.get(row['rule_id'],0)+1
    print(json.dumps({"records_evaluated":count,"rules_enabled":sum(rule.enabled for rule in rules.rules),"triggered_evaluations":len(evaluations),"by_rule":counts},indent=2))
if __name__=='__main__': main()
