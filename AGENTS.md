# Notes for coding agents

## Project

DriveAnalytics is a public crash-analytics app built on real data:

- NHTSA FARS: every fatal US crash.
- NYC Open Data Motor Vehicle Collisions: every police-reported NYC crash since 2012.

It began as a synthetic autonomous-vehicle telemetry demo, and that data and code are gone.

## Rules

- Keep claims honest. No invented metrics, benchmark speedups or accuracy numbers; report only what was measured, with the environment.
- Never add crash footage or victim-identifying information. Location imagery (for example Mapillary) is fine.
- Check source formats against real files or the live API before changing a loader, and record what you checked in `docs/DATA_SOURCES.md`.
- Tests must not download anything. Build fixture files inside the test (see `backend/tests/conftest.py`).

## Layout

- `backend/pipeline/`: `fars.py`, `nyc.py` and the CLI in `__main__.py`.
  - Run `python -m pipeline fars --years 2020-2024` or `python -m pipeline nyc [--since DATE]`.
- `backend/config/risk_flags.yaml`: risk-flag rules, evaluated by `backend/app/services/rule_engine.py`.
- `backend/app/`: FastAPI app and SQLAlchemy models. PostgreSQL is the target, and SQLite is used in tests.
- `frontend/`: React + TypeScript + Vite.

## Roadmap

1. Data loading. Done.
2. Map drill-down: US, then state, then county or city, then roads and crash dots. Done (FARS).
3. API: crashes near a point or route (PostGIS), intersections ranked by severity, year-over-year trends.
4. UI: address search, an NYC street-level view with all crashes, trend charts, and street-level imagery via Mapillary.
5. Deploy and docs. Switch map tiles from tile.openstreetmap.org to a provider with an account before a public deploy.
