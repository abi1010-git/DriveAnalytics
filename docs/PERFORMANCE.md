# SafeDrive Performance Analysis

## Environment

- Operating system: Windows (Windows 11 family; local development machine)
- Python: 3.14.6
- PostgreSQL: 17.11, 64-bit
- Hardware: Lenovo 82X7, 12 logical processors, 15.7 GB RAM
- Database: local PostgreSQL on `127.0.0.1:5432`
- Dataset: 100 vehicles, 1,000,000 telemetry records, 62,792 safety events
- Generation time: 75.69 seconds using deterministic seed 42 and 20,000-row batches

## Methodology

`backend/scripts/generate_data.py` generated the dataset with seed 42 and batch inserts. The benchmark script ran four queries corresponding to existing SafeDrive behavior: vehicle telemetry retrieval, telemetry surrounding a selected event, time-range event aggregation, and vehicle/route event aggregation.

Each query was executed 10 times in one PostgreSQL session. Timings use Python `time.perf_counter()` around the SQLAlchemy execution and are reported in milliseconds. Each run also captured `EXPLAIN (ANALYZE, BUFFERS)` output. The optimized run added only the composite telemetry index selected from the baseline plan:

```sql
CREATE INDEX ix_telemetry_vehicle_timestamp
ON telemetry (vehicle_id, timestamp);
```

The benchmark is local and warm-cache behavior is likely after the first query. It is intended for reproducibility, not production capacity planning.

## Baseline Results

| Query | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|---:|
| telemetry_by_vehicle_and_time | 21.6662 | 21.9746 | 20.7027 | 22.4806 |
| recent_telemetry_around_event | 0.3037 | 0.2696 | 0.1848 | 0.6511 |
| events_by_time_range | 18.3712 | 18.1988 | 17.5771 | 20.1134 |
| events_by_vehicle_and_route | 11.3905 | 11.4606 | 10.8966 | 11.8124 |

## Query Plan Analysis

- `telemetry_by_vehicle_and_time` used the existing `vehicle_id` index, then filtered timestamps and sorted the matching rows. The full-period range selected nearly all telemetry for the vehicle, so a composite index was not selected by the planner for this broad query.
- `recent_telemetry_around_event` initially used the timestamp index and then filtered by vehicle. This is the selective application pattern that benefits from `(vehicle_id, timestamp)`.
- `events_by_time_range` used a sequential scan followed by `HashAggregate`. The selected range covered nearly the complete event table, so an index would not avoid reading most rows.
- `events_by_vehicle_and_route` used a sequential scan and `HashAggregate`, which is appropriate for a full-table aggregation at this dataset size.

## Optimizations

The measured plan for nearby telemetry showed a timestamp lookup followed by a vehicle filter. The composite `telemetry(vehicle_id, timestamp)` index was added because it matches both predicates and supports the timestamp ordering. No event aggregation index was retained: the baseline and follow-up plans continued to use sequential scans because the tested ranges covered almost all events.

## Optimized Results

| Query | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|---:|
| telemetry_by_vehicle_and_time | 21.3950 | 21.3401 | 20.7795 | 22.4665 |
| recent_telemetry_around_event | 0.3695 | 0.2804 | 0.1955 | 0.9049 |
| events_by_time_range | 17.3758 | 17.3269 | 16.6682 | 18.3797 |
| events_by_vehicle_and_route | 11.1038 | 11.0261 | 10.6225 | 12.1410 |

The optimized plan for `recent_telemetry_around_event` used `ix_telemetry_vehicle_timestamp` with both the vehicle and timestamp predicates. The broad telemetry query still used the single-column vehicle index because its range returned about 10,000 rows.

## Comparison

| Query | Before mean (ms) | After mean (ms) | Calculated change |
|---|---:|---:|---:|
| telemetry_by_vehicle_and_time | 21.6662 | 21.3950 | 1.25% lower |
| recent_telemetry_around_event | 0.3037 | 0.3695 | 21.66% higher |
| events_by_time_range | 18.3712 | 17.3758 | 5.42% lower |
| events_by_vehicle_and_route | 11.3905 | 11.1038 | 2.52% lower |

These timing differences are small enough to be affected by local cache and scheduling noise. The durable result is the changed selective query plan; the benchmark does not claim a latency improvement for every query.

## Limitations

- All telemetry, vehicles, and events are synthetic.
- Benchmarks ran on a local Windows development machine with a warm PostgreSQL session.
- The workload is not representative of production autonomous-vehicle systems.
- No production traffic, concurrency, replication, storage latency, or network latency was measured.
- PostgreSQL credentials are not stored in the repository.
