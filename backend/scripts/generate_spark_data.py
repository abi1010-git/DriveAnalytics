"""Export the configured synthetic telemetry database to Parquet for Spark."""
import argparse
import os
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import Telemetry, Vehicle


def main():
    parser = argparse.ArgumentParser(description="Export synthetic telemetry to Parquet")
    parser.add_argument("--output", type=Path, default=Path("data/raw/telemetry"))
    parser.add_argument("--telemetry-count", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=50000)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    db = SessionLocal()
    writer = None
    count = 0
    schema = pa.schema([
        ("id", pa.int64()), ("vehicle_id", pa.int32()), ("timestamp", pa.timestamp("us")),
        ("speed_mph", pa.float64()), ("acceleration_mps2", pa.float64()), ("steering_angle", pa.float64()),
        ("brake_pressure", pa.float64()), ("battery_percent", pa.float64()), ("sensor_status", pa.string()),
        ("route_id", pa.string()), ("software_version", pa.string()),
    ])
    try:
        stmt = select(Telemetry, Vehicle.software_version).join(Vehicle).order_by(Telemetry.id)
        if args.telemetry_count:
            stmt = stmt.limit(args.telemetry_count)
        result = db.execute(stmt).yield_per(args.batch_size)
        while rows := result.fetchmany(args.batch_size):
            records = [{**telemetry.__dict__, "software_version": version} for telemetry, version in rows]
            for record in records: record.pop("_sa_instance_state", None)
            table = pa.Table.from_pylist(records, schema=schema)
            if writer is None: writer = pq.ParquetWriter(args.output, table.schema, compression="snappy")
            writer.write_table(table)
            count += len(records)
    finally:
        if writer: writer.close()
        db.close()
    print(f"Exported {count} synthetic telemetry records to {args.output} in {time.perf_counter() - started:.2f}s")


if __name__ == "__main__": main()
