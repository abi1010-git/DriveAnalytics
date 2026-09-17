# SafeDrive Development Session Notes

## Project

SafeDrive is a portfolio project called **SafeDrive: Autonomous Vehicle Safety Analytics Platform**. It is an internal engineering-style analytics tool using entirely synthetic autonomous-vehicle telemetry and safety events. It must not claim affiliation with, or be based on, any proprietary autonomous-vehicle system.

## User goals

- Demonstrate full-stack engineering, data processing, SQL, API development, and performance optimization.
- Use React, TypeScript, Vite, Recharts, Python, FastAPI, SQLAlchemy, Pydantic, pytest, PostgreSQL, and SQLite fallback.
- Build incrementally: data model, synthetic data generation, FastAPI API, React dashboard, event investigation, tests, and documentation.
- Do not implement future phases yet: PySpark, large-scale telemetry processing, SQL benchmarking, Docker, or YAML safety-rule configuration.

## Repository

The project was created from an initially empty workspace at:

`C:\Users\abhij\OneDrive\Desktop\GithubProject\safedrive`

Main structure:

```text
safedrive/
  backend/
    app/
      main.py
      database.py
      models/
      schemas/
      routes/
      services/
    scripts/generate_data.py
    tests/test_api.py
    requirements.txt
  frontend/
    package.json
    index.html
    tsconfig.json
    src/main.tsx
    src/style.css
    src/vite-env.d.ts
  data/
  docs/
  README.md
  AGENTS.md
  .env.example
  .gitignore
```

## Implemented backend

- SQLAlchemy models for `Vehicle`, `Telemetry`, and `SafetyEvent`.
- SQLite is the default database; PostgreSQL can be selected through `DATABASE_URL`.
- FastAPI endpoints:
  - `GET /health`
  - `GET /api/vehicles`
  - `GET /api/events`
  - `GET /api/events/{event_id}`
  - `GET /api/metrics/summary`
  - `GET /api/vehicles/{vehicle_id}/telemetry`
- Event filters support vehicle, event type, severity, software version, route, and date ranges.
- Event details include nearby telemetry lookup within a 10-minute window.
- Summary metrics include totals, grouped counts, hard-braking count, and sensor-failure count.
- CORS allows the Vite frontend at `http://localhost:5173`.

## Synthetic data

`backend/scripts/generate_data.py` uses deterministic random seed `42` and creates:

- 20 simulated vehicles
- 5,000 telemetry records
- Approximately 100–300 safety events; the current generated dataset contains 303 events

Events are related to telemetry signals. Examples include hard braking from strong negative acceleration, sensor failures from degraded sensor status, speed-threshold events from unusually high speed, rapid acceleration, and simulated near collisions.

All data is synthetic. Never add real vehicle, customer, driver, or proprietary system data.

## Implemented frontend

- React + TypeScript + Vite dashboard.
- Professional dark engineering-console visual style.
- Summary cards for vehicles, safety events, critical events, hard braking, and sensor failures.
- Recharts charts for event severity, event type, and software version distributions.
- Event investigation table with severity filtering.
- Clickable event details panel showing event metadata and API reference for nearby telemetry.

## Verification history

- Synthetic data generation succeeded with 20 vehicles, 5,000 telemetry records, and 303 events.
- Backend tests pass: `3 passed`.
- Frontend production build succeeds with `npm.cmd run build`.
- Vite reports a non-failing bundle-size warning because the generated JavaScript chunk is over 500 kB.
- Pytest emits deprecation warnings related to the installed Starlette/httpx combination, but tests pass.
- No benchmark results have been fabricated or claimed.

## Local setup

Backend:

```powershell
cd C:\Users\abhij\OneDrive\Desktop\GithubProject\safedrive\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_data.py
uvicorn app.main:app --reload
```

Frontend, in a second PowerShell window:

```powershell
cd C:\Users\abhij\OneDrive\Desktop\GithubProject\safedrive\frontend
npm.cmd install
npm.cmd run dev
```

Open the dashboard at `http://localhost:5173/`. API docs are at `http://127.0.0.1:8000/docs`.

Use `DATABASE_URL` from `.env.example` to configure PostgreSQL. Never commit secrets.

## Important environment issue

During the session, Node.js/npm initially worked during frontend installation and build, but later became unavailable from the active PowerShell PATH. `node`, `npm`, and `winget` were not recognized, and the prior WinGet package path was no longer usable. Because of this, the assistant could not reliably restart the frontend server or install Node.js automatically. If localhost is unreachable, install Node.js LTS from `https://nodejs.org/`, restart PowerShell, verify `node --version` and `npm --version`, then run the frontend commands above.

The backend port can also be blocked or occupied on Windows. If needed, use another port such as `8001` and update the frontend API base URL in `frontend/src/main.tsx` accordingly.

## Future Phase 2

- PySpark telemetry processing
- PostgreSQL query optimization
- Honest performance benchmarking using measured results
- Configurable YAML safety-rule engine
- Dockerized deployment
- Rich telemetry charts rendered directly in the event details panel

