# SafeDrive: Autonomous Vehicle Safety Analytics Platform

SafeDrive is a portfolio-grade internal engineering analytics tool built around entirely simulated autonomous-vehicle telemetry and safety events. It is not affiliated with, based on, or representative of any proprietary vehicle system.

## Overview

The MVP generates reproducible telemetry for 20 simulated vehicles, derives safety events from signal thresholds, stores the data in SQLite (or PostgreSQL), and exposes a typed FastAPI API consumed by a React dashboard.

```text
Synthetic Telemetry Generator
          |
          v
   PostgreSQL / SQLite
          |
          v
      FastAPI API
          |
          v
  React + TypeScript
          |
          v
 Safety Analytics Dashboard
```

## Features and stack

FastAPI, SQLAlchemy, Pydantic, pytest, React, TypeScript, Vite, Recharts, PySpark, and Parquet. Features include summary metrics, event filters, event details, nearby telemetry API lookup, and Spark-derived fleet summaries.

## Local setup

```powershell
cd safedrive/backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_data.py
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd safedrive/frontend
npm.cmd install
npm.cmd run dev
```

Set `DATABASE_URL` from `.env.example` to use PostgreSQL. Never commit credentials.

## API overview

`GET /health`, `/api/vehicles`, `/api/events` (vehicle, event type, severity, version, route, and date filters), `/api/events/{id}`, `/api/metrics/summary`, and `/api/vehicles/{id}/telemetry` (date filters). Swagger is available at `/docs`.

## Synthetic data

The generator uses seed 42 and creates only simulated values. Hard braking, sensor failure, high speed, and acceleration events are derived from corresponding telemetry records.

## Testing

```powershell
cd safedrive/backend
pytest
cd ..\frontend
npm.cmd run build
```

## Performance Engineering

Phase 2 includes PostgreSQL support, configurable batch generation, and a reproducible SQL benchmark. The measured benchmark dataset contains 100 vehicles, 1,000,000 synthetic telemetry records, and 62,792 synthetic safety events in local PostgreSQL 17. The tested queries cover vehicle telemetry ranges, telemetry surrounding an event, event aggregation by time range, and aggregation by vehicle and route. The measured optimization is a composite `(vehicle_id, timestamp)` telemetry index selected from `EXPLAIN ANALYZE` for the nearby-telemetry lookup.

Run the benchmark with PostgreSQL credentials supplied through the environment or a local PostgreSQL password file:

```powershell
cd safedrive/backend
$env:DATABASE_URL = "postgresql+psycopg2://postgres@127.0.0.1:5432/safedrive"
python scripts/generate_data.py --vehicles 100 --telemetry-count 1000000 --batch-size 20000
python scripts/benchmark_queries.py --runs 10 --output baseline.json
python scripts/benchmark_queries.py --runs 10 --optimize --output optimized.json
```

See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for the actual measured results, query plans, methodology, and limitations. SafeDrive remains a portfolio engineering project and is not production-ready.

The PySpark batch pipeline is documented in [docs/SPARK_PIPELINE.md](docs/SPARK_PIPELINE.md). Configurable YAML safety rules and explainable evaluations are documented in [docs/SAFETY_RULE_ENGINE.md](docs/SAFETY_RULE_ENGINE.md).

## Future improvements (Phase 3+)

PySpark processing, a configurable YAML safety-rule engine, richer telemetry charts in the event panel, Dockerized deployment, and broader production-style performance testing.
