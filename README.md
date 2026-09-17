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

FastAPI, SQLAlchemy, Pydantic, pytest, React, TypeScript, Vite, and Recharts. Features include summary metrics, event filters, event details, and nearby telemetry API lookup.

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

## Future improvements (Phase 2)

PySpark processing, PostgreSQL query optimization, honest performance benchmarking, a configurable YAML safety-rule engine, richer telemetry charts in the event panel, and Dockerized deployment.
