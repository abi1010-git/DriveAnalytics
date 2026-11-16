# DriveAnalytics

**Where do crashes happen, when, and why: built on real US crash records.**

DriveAnalytics loads two public datasets into PostgreSQL and makes them searchable:

- **NHTSA FARS**: every fatal crash on a US public road, with location, time, weather, lighting, road type, and whether speeding or a drinking driver was involved.
- **NYC Open Data Motor Vehicle Collisions**: every police-reported crash in New York City since July 2012, with coordinates, injuries and up to five contributing factors.

The goal is a tool anyone can use to look up crash history near an address or along a route, see which intersections are most dangerous by severity rather than raw counts, and understand what conditions show up in crashes near them.

## Explore the map

![US map shaded by traffic deaths per state, 2020–2024](docs/images/us-map.jpg)

1. **Start with the country.** States are shaded by the number of people killed in crashes from 2020 to 2024.
2. **Click a state.** Its counties are shaded the same way, and the state's cities with the most deaths appear as bubbles and in a list.
3. **Click a county or a city.** Every fatal crash appears as a dot on a street map. The side panel shows:
   - the roads with the most deaths, and for each road the share of its crashes that involved speeding, a drinking driver, or a pedestrian or cyclist
   - what police recorded (dark roads, bad weather, intersections and so on)
   - the time of day
4. **Click a road** to light up its crashes, or **click a dot** for one crash's details.

![Wayne County, Michigan, with fatal crashes on I-94 highlighted](docs/images/wayne-county-i94.jpg)

These are totals, not rates. A busy interstate will rank high partly because so many people drive it, and the app says so.

### Up to now, not just 2024

FARS is the only nationwide crash dataset, and it is published about 1.5 years late. To reach 2026 and today, the map adds local sources wherever they exist:

- **Police crash reports** (blue dots) from NYC and Chicago. These are about a day behind, with injury and death counts.
- **Live incidents** (purple dots) from six feeds: California Highway Patrol, Washington state highways, 511NJ/TRANSCOM (NJ + NY), Austin, Seattle and San Francisco. These are minutes old, and they are clearly labeled as unverified first reports.

Use the **From/to** years (2012 to now) or **Last 24 hours**. The side panel says which sources cover the area and how fresh each one is. Sources and their limits are listed in [`docs/LIVE_AND_RECENT_SOURCES.md`](docs/LIVE_AND_RECENT_SOURCES.md).

## Status

| Phase | What | State |
|---|---|---|
| 1. Data | Reproducible download + load of FARS and NYC into PostgreSQL, risk-factor flags, tests | **Done** |
| 3a. Map | State → county/city drill-down, roads ranked by deaths, crash dots with details, factor and time-of-day breakdowns | **Done** |
| 3b. Recent + live | 2012–2026 time range; NYC + Chicago crash reports; 6 live incident feeds polled every 10 min | **Done** |
| 2. API | Crashes near a point or route (PostGIS), intersections ranked by severity, year-over-year trends | Next |
| 3c. More sources | Iowa + Utah statewide, DC, Denver, Nashville and other crash-report portals (researched); free-key 511 feeds (AZ, GA, PA, NY, OH) | Next |
| 3d. UI | Address search, trends, street-level imagery of a location (Mapillary) | Planned |
| 4. Deploy | Hosted demo, docs | Planned |

### What's loaded today (local run, Nov 2026)

| Dataset | Rows | Notes |
|---|---:|---|
| FARS 2020–2024 | 189,208 fatal crashes, 205,237 deaths | 188,403 (99.6%) have usable coordinates |
| NYC crashes, Jul 2012 – Nov 2026 | 2,305,623 crashes, 779,449 people injured, 3,746 killed | 2,056,192 (89.2%) have usable coordinates |

These are counts from this project's own load, not official statistics. NHTSA and NYPD publish their own totals.

## How it works

```mermaid
flowchart LR
    A[FARS yearly zips] --> L[pipeline/fars.py]
    B[NYC SODA API] --> R[raw .jsonl.gz cache] --> N[pipeline/nyc.py]
    Y[risk_flags.yaml] --> L & N
    L & N --> P[(PostgreSQL)] --> F[FastAPI] --> W[React]
```

- **Loaders** (`backend/pipeline/`):
  - They download and cache the raw files, clean them, and load PostgreSQL in batches.
  - They're safe to re-run: a FARS year is replaced in one transaction, and NYC rows are upserted.
  - Source quirks, such as FARS's `77.7777` "unknown latitude" codes and NYC's 0/0 coordinates, are handled and documented in [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).
- **Risk flags** (`backend/config/risk_flags.yaml`):
  - Readable YAML rules such as "speeding involved", "dark, no street lighting" or "pedestrian injured", attached to each crash at load time.
  - The rule engine accepts only whitelisted fields and operators and never executes code. See [`docs/RISK_FLAGS.md`](docs/RISK_FLAGS.md).
- **API**: FastAPI. Endpoints are listed in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- **Map**:
  - React + Leaflet.
  - State and county boundaries come from the Census Bureau via `us-atlas`, and are joined to FARS on FIPS codes.
  - Street tiles come from OpenStreetMap, darkened with CSS. OSM's free tile servers are meant for light use, so a public deploy should switch to a tile provider with an account.

## Run it locally

Requires Python 3.12+, Node 22+ and PostgreSQL. SQLite works for quick tries, but the NYC load is large.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Point at PostgreSQL (keep the password in pgpass.conf, not here)
$env:DATABASE_URL = "postgresql+psycopg2://postgres@127.0.0.1:5432/driveanalytics"

python -m pipeline fars --years 2020-2024   # ~170 MB download, a few minutes
python -m pipeline nyc                       # ~2.3M rows; took ~7 min to download + ~23 min to load here
python -m pipeline nyc --since 2026-11-01    # later: only rows added or amended since a date
python -m pipeline chicago                   # ~1.1M Chicago crash reports
python -m pipeline live --backfill-days 30   # poll the 6 live feeds once (first run fetches 30 days where the feed has history)
python -m pipeline live --every 10           # keep polling every 10 minutes (leave running)

uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev     # http://localhost:5173
```

The API accepts browser requests only from `http://localhost:5173` by default. If Vite picks another port, set `CORS_ORIGINS=http://localhost:<port>` before starting the backend. If the API isn't on port 8000, set `VITE_API_BASE_URL` before starting the frontend.

With Docker:

1. Copy `.env.docker.example` to `.env` and set a password.
2. Run `docker compose up --build -d`.
3. Run `docker compose run --rm backend python -m pipeline fars`.

## Tests

```powershell
cd backend
pytest
```

The tests build small FARS zips and NYC files in their real formats, including a cp1252-encoded FARS file, so CI never downloads anything. They cover:

- parsing and "unknown" codes
- encoding fallback
- re-run safety
- upsert of amended NYC records
- keyset paging
- rule validation
- API filters

## Limits

- FARS covers only crashes in which someone died, so it shows where people die, not where most crashes happen.
- NYC data is preliminary, and contributing factors are an officer's judgment at the scene.
- Each state records road names its own way. The loader merges spellings of the same route ("I-45", "I-45/NORTH FWY" and "I-45/GULF FWY" all become I-45), but a road can still show up twice when some crashes were written by route number and others by street name ("FM-1093" and "WESTHEIMER RD").
- Neither dataset includes traffic volume, so a busy road will show more crashes than a quiet one without being riskier per trip. Rankings will say this clearly.
- No crash footage is used or linked. Location imagery (Phase 3) shows what a place looks like, not the crash.

## History

This repository began as **SafeDrive**, a demo built on one million rows of synthetic self-driving-car telemetry. It was rebuilt on real data because synthetic data couldn't answer any real question. The FastAPI/PostgreSQL backend, the YAML rule engine (now risk flags), the tests, CI and Docker setup carried over. The synthetic data, its generators, the Spark job and the benchmark that went with them were removed.
