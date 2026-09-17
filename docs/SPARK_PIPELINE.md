# SafeDrive Telemetry Processing Pipeline

## Purpose

PySpark provides a batch-processing path for larger synthetic telemetry files. It processes Parquet with DataFrame transformations and writes compact summaries for the application. PostgreSQL remains the application and SQL-performance database; Spark does not replace it.

## Architecture

```text
Synthetic telemetry -> Parquet -> PySpark
                                  +-> processed telemetry Parquet
                                  +-> vehicle/route/time/software summaries
                                  v
                            PostgreSQL summaries -> FastAPI -> React
```

## Input Schema

The raw Parquet export contains `vehicle_id`, `timestamp`, `speed_mph`, `acceleration_mps2`, `steering_angle`, `brake_pressure`, `battery_percent`, `sensor_status`, `route_id`, and `software_version`.

## Transformations

The pipeline validates the expected schema, casts numeric fields, drops records missing vehicle or timestamp, and fills non-key missing values with explicit defaults. Illustrative synthetic thresholds derive absolute acceleration, hard braking, rapid acceleration, speed-threshold, sensor-failure, safety-condition, and telemetry-health fields. These thresholds are not real autonomous-vehicle safety standards.

## Window Analysis

Rows are partitioned by vehicle and ordered by timestamp. A Spark window calculates previous speed and speed change for each vehicle, demonstrating temporal processing rather than only grouping.

## Aggregations

The pipeline writes processed telemetry plus vehicle, route, hourly time, and software-version Parquet summaries. Vehicle summaries are also loaded into PostgreSQL tables exposed by `GET /api/analytics/fleet-summary`; route summaries are exposed by `GET /api/analytics/routes`.

## Running the Pipeline

From `backend`, with PostgreSQL credentials supplied through the local password file or environment:

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
$env:HADOOP_HOME = "C:\Users\abhij\hadoop"
$env:Path = "$env:JAVA_HOME\bin;$env:HADOOP_HOME\bin;$env:Path"
$env:DATABASE_URL = "postgresql+psycopg2://postgres@127.0.0.1:5432/safedrive"
python scripts/generate_spark_data.py --output data/raw/telemetry.parquet --telemetry-count 1000000
python -m pipeline.process_telemetry --input data/raw/telemetry.parquet --output data/processed
```

Use `--no-postgres` when only Parquet outputs are desired. The generated data directories are ignored by Git.

## Validation Results

On this Windows development machine, the pipeline exported 1,000,000 records from PostgreSQL to Parquet in 24.34 seconds and processed 1,000,000 records in 33.71 seconds with Spark 4.2.0 and Java 17.0.20.1. It produced 1,000,000 processed rows, 100 vehicle summaries, 6 route summaries, 1,669 hourly summaries, and 3 software-version summaries.

## Limitations

- All telemetry is synthetic.
- Thresholds are illustrative and not a real safety system.
- Local Spark processing is not representative of a distributed production Spark cluster.
- Windows requires the local Hadoop helper configuration for Spark file output.
