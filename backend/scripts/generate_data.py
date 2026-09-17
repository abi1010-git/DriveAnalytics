"""Create reproducible synthetic SafeDrive data, including large benchmark datasets."""
import argparse
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert

from app.database import Base, SessionLocal, engine
from app.models import SafetyEvent, Telemetry, Vehicle

VERSIONS = ["sim-1.0", "sim-1.1", "sim-2.0"]
ROUTES = [f"R-{i:02d}" for i in range(1, 7)]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic SafeDrive data")
    parser.add_argument("--vehicles", type=int, default=20)
    parser.add_argument("--telemetry-count", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=10000)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.vehicles <= 0 or args.telemetry_count <= 0 or args.batch_size <= 0:
        raise SystemExit("vehicles, telemetry-count, and batch-size must be positive")
    rng = random.Random(args.seed)
    started = time.perf_counter()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        vehicle_rows = [{"vehicle_name": f"SD-{i:03d}", "software_version": rng.choice(VERSIONS), "status": rng.choice(["ACTIVE", "MAINTENANCE", "STANDBY"])} for i in range(1, args.vehicles + 1)]
        db.execute(insert(Vehicle), vehicle_rows)
        db.commit()
        telemetry_count = event_count = 0
        start = datetime(2026, 1, 1)
        for batch_start in range(0, args.telemetry_count, args.batch_size):
            batch_end = min(batch_start + args.batch_size, args.telemetry_count)
            telemetry_rows, event_rows = [], []
            for index in range(batch_start, batch_end):
                vehicle_id = index % args.vehicles + 1
                slot = index // args.vehicles
                timestamp = start + timedelta(minutes=slot * 10 + vehicle_id)
                speed = max(0, rng.gauss(32, 12))
                acceleration = rng.gauss(0, 0.8)
                sensor_status = "DEGRADED" if rng.random() < 0.025 else "OK"
                route_id = rng.choice(ROUTES)
                telemetry_rows.append({"vehicle_id": vehicle_id, "timestamp": timestamp, "speed_mph": round(speed, 2), "acceleration_mps2": round(acceleration, 2), "steering_angle": round(rng.gauss(0, 8), 2), "brake_pressure": round(max(0, rng.gauss(18, 12)), 2), "battery_percent": round(max(0, 100 - slot * 0.018 - rng.random() * 3), 2), "sensor_status": sensor_status, "route_id": route_id})
                kind = None
                if acceleration < -2.2: kind = "HARD_BRAKING"
                elif sensor_status != "OK": kind = "SENSOR_FAILURE"
                elif speed > 58: kind = "SPEED_THRESHOLD"
                elif acceleration > 2.2: kind = "RAPID_ACCELERATION"
                elif rng.random() < 0.018: kind = "NEAR_COLLISION_SIMULATED"
                if kind:
                    severity = "CRITICAL" if kind in ("SENSOR_FAILURE", "NEAR_COLLISION_SIMULATED") and rng.random() < 0.25 else rng.choice(["LOW", "MEDIUM", "HIGH"])
                    event_rows.append({"vehicle_id": vehicle_id, "timestamp": timestamp, "event_type": kind, "severity": severity, "description": f"Simulated {kind.lower().replace('_', ' ')} detected from telemetry.", "software_version": vehicle_rows[vehicle_id - 1]["software_version"], "route_id": route_id})
            db.execute(insert(Telemetry), telemetry_rows)
            if event_rows: db.execute(insert(SafetyEvent), event_rows)
            db.commit()
            telemetry_count += len(telemetry_rows)
            event_count += len(event_rows)
    finally:
        db.close()
    print(f"Created {args.vehicles} vehicles, {telemetry_count} telemetry records, {event_count} events in {time.perf_counter() - started:.2f}s")


if __name__ == "__main__":
    main()
