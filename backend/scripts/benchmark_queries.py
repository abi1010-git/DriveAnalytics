"""Measure SafeDrive PostgreSQL queries and optionally apply evidence-based indexes."""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

from sqlalchemy import create_engine, text

QUERIES = {
    "telemetry_by_vehicle_and_time": """
        SELECT id, vehicle_id, timestamp, speed_mph, acceleration_mps2, route_id
        FROM telemetry
        WHERE vehicle_id = :vehicle_id AND timestamp BETWEEN :start_time AND :end_time
        ORDER BY timestamp
    """,
    "recent_telemetry_around_event": """
        SELECT id, vehicle_id, timestamp, speed_mph, acceleration_mps2, route_id
        FROM telemetry
        WHERE vehicle_id = :vehicle_id AND timestamp BETWEEN :start_time AND :end_time
        ORDER BY timestamp
    """,
    "events_by_time_range": """
        SELECT severity, event_type, software_version, count(*)
        FROM safety_events
        WHERE timestamp BETWEEN :start_time AND :end_time
        GROUP BY severity, event_type, software_version
    """,
    "events_by_vehicle_and_route": """
        SELECT vehicle_id, route_id, count(*)
        FROM safety_events
        GROUP BY vehicle_id, route_id
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_telemetry_vehicle_timestamp ON telemetry (vehicle_id, timestamp)",
]


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--optimize", action="store_true", help="Create indexes selected after baseline analysis")
    p.add_argument("--output", type=Path, default=None)
    return p.parse_args()


def parameters(conn):
    row = conn.execute(text("SELECT vehicle_id, min(timestamp), max(timestamp) FROM telemetry GROUP BY vehicle_id ORDER BY vehicle_id LIMIT 1")).one()
    event = conn.execute(text("SELECT vehicle_id, timestamp FROM safety_events ORDER BY id LIMIT 1")).one()
    return {"vehicle_id": row[0], "start_time": row[1], "end_time": row[2], "event_vehicle_id": event[0], "event_time": event[1]}


def main():
    config = args()
    url = os.getenv("DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        raise SystemExit("Set DATABASE_URL to a PostgreSQL database before running this benchmark.")
    engine = create_engine(url)
    with engine.begin() as conn:
        if config.optimize:
            for statement in INDEXES:
                conn.execute(text(statement))
            conn.execute(text("ANALYZE telemetry"))
            conn.execute(text("ANALYZE safety_events"))
        p = parameters(conn)
        values = {"vehicle_id": p["vehicle_id"], "start_time": p["start_time"], "end_time": p["end_time"]}
        values_around = {"vehicle_id": p["event_vehicle_id"], "start_time": p["event_time"], "end_time": p["event_time"]}
        results = {}
        plans = {}
        for name, sql in QUERIES.items():
            bind = values_around if name == "recent_telemetry_around_event" else values
            timings = []
            for _ in range(config.runs):
                started = time.perf_counter()
                conn.execute(text(sql), bind).all()
                timings.append((time.perf_counter() - started) * 1000)
            plan = conn.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + sql), bind).scalars().all()
            results[name] = {"runs": config.runs, "mean_ms": statistics.mean(timings), "median_ms": statistics.median(timings), "min_ms": min(timings), "max_ms": max(timings)}
            plans[name] = list(plan)
    output = {"database": url.split("@")[-1], "optimized": config.optimize, "results": results, "plans": plans}
    print(json.dumps(output, indent=2, default=str))
    if config.output:
        config.output.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
