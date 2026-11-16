# Static site (GitHub Pages)

The public site runs with no server. `python -m pipeline export` reads the local database and
writes everything the map needs as JSON files. The frontend, built with `VITE_STATIC=1`, reads
those files instead of calling the API, and does the filtering and summing in the browser.

What changes compared with running the API locally:

- **Freshness:** the data is as fresh as the last export. Its time is shown in the panel
  ("Data as of ..."), and "Last 24 hours" means the 24 hours before the export.
- **Crash dots for recent sources:** only for the 12 months before the export, at most
  `tile_cap` per source per 1° tile (newest first). Counts are kept for every year.
- **Recent-source counts for an area:** summed from a 0.05° grid (about 5 km), so an area's
  box is rounded out to whole cells. The API version uses the exact box, and both include
  some of the neighbors (the panel already says so).
- FARS is exported in full, so every FARS view matches the API exactly.

## Files

All paths are relative to `data/` next to `index.html`. Every file is JSON. Rows are arrays,
not objects, to keep the files small; the column order is listed below.

### `meta.json`

```json
{
  "generated_at": "2026-11-16T20:00:00Z",
  "fars_years": [2020, 2021, 2022, 2023, 2024],
  "recent_years": [2012, ..., 2026],
  "dot_days": 365,
  "dots_since": "2025-11-16T20:00:00",
  "grid_deg": 0.05,
  "tile_deg": 1,
  "tile_cap": 5000,
  "tiles": ["-123_37", "-74_40", ...]
}
```

`tiles` lists every tile file that exists (key `"{x}_{y}"` with `x = floor(lon)`, `y = floor(lat)`).

### `flags.json`

The same `FlagDef[]` the API's `/api/risk-flags?counts=false` returns.

### `coverage.json`

The same `Coverage[]` as `/api/recent/coverage`.

### `fars/states.json`

`[state_code, name, year, crashes, deaths]` per state and year.

### `fars/{SS}.json` (SS = two-digit state FIPS, e.g. `06`)

```json
{
  "counties": {"37": "Los Angeles", ...},
  "crashes": [[id, year, county_code, lat, lon, date, hour, deaths, road_name, road_route,
               city_name, light_condition, weather, first_harmful_event, [flag ids],
               speeding, drinking, non_motorist], ...]
}
```

- `counties` maps each county code to its FARS name.
- The crash list holds every FARS crash in the state, including the 0.4% without coordinates
  (lat/lon null).
- `speeding`, `drinking` and `non_motorist` are 0/1. They match the API's road counts:
  `speeding_involved`, `drinking_driver_involved` and `pedestrians > 0`.

From this the browser computes, exactly as `backend/app/services/map_queries.py` does:

- **counties:** group by county_code. `name` is the county's name, and `fips` is SS + the
  three-digit code. Sort by deaths, descending.
- **cities:** group by city_name, skipping nulls. `county_code` is the max, and lat/lon are
  averaged over crashes that have coordinates. Sort by deaths, then crashes, descending. Keep 25.
- **roads:** group by road_route, skipping nulls. Sort by deaths, then crashes (both
  descending), then route. Keep 10. `name` is the most common road_name for that route in the
  area; ties go to the greater name.
- **factors:** total crashes, total deaths, and for each flag id the number of crashes that
  have it, sorted descending.
- **hours:** 24 rows of `{hour, crashes}`.
- **crash points:** crashes with coordinates, sorted by date descending, then id.

Each of these is filtered to the selected county (county_code) or city (city_name) and to the
year range.

### `recent/totals.json`

`[source, year, count, killed, injured, first, last]` per source and year, over all of that
source's rows (with or without coordinates). This is used when no area is selected (the US
view). For the US view, `with_coordinates` comes from the grid sum. Times are ISO strings in
the same convention as the API: local time for records, UTC without a suffix for live
incidents.

### `recent/grid-{year}.json`

```json
{"sources": ["california", "nyc", ...], "cells": [[source_index, x, y, count, killed, injured], ...]}
```

`x = floor(lon / 0.05)` and `y = floor(lat / 0.05)`. Only rows with coordinates are counted.
Live sources count only `category == "crash"`, which is the API's default.

For an area box `[w, s, e, n]`, a cell counts if `floor(w/0.05) <= x <= floor(e/0.05)` and the
same holds for y. A source's summary for the range is:

- **count, killed, injured:** summed over the cells in the box and the years in the range.
  Killed and injured are null when the source never reports them (null in totals).
- **first, last:** the earliest `first` and latest `last` from `totals.json` across the range's
  years. These are source-wide values, not limited to the box.
- **with_coordinates:** the count.

Sources with count 0 are dropped, and the rest are sorted by count, descending. The result has
the shape of `RecentSource[]`, with `kind` and `label` taken from coverage.

### `recent/tiles/{x}_{y}.json`

`[source, id, time, lat, lon, killed, injured, road, category, type]`: the newest rows of each
source within the dot window, up to `tile_cap` per source. Live sources contribute only crash
rows. Each file is sorted by time, descending.

The browser loads the tiles that overlap the box, keeps the rows inside the box and the year
range, and returns the newest 3000 per kind (record or live), matching the API's
3000-per-table limit. Each row's `kind` comes from coverage.

### `live/last24h.json`

```json
{"summary": [RecentSource...], "points": [RecentPoint...]}
```

Every live incident in the 24 hours before the export, all categories (the API's
`all_incidents=true`), as objects in the API's own shapes. The browser filters the points by
box and recomputes the summary per source from the points in the box. Incidents without
coordinates count only in the US view, which uses `summary` as is.

## Publishing

1. `python -m pipeline export --out ../frontend/public/data`
2. In `frontend`: `VITE_STATIC=1 npx vite build --base=/DriveAnalytics/`

The `pages` workflow does step 2 on GitHub. It downloads the data from the `data-latest`
release (`site-data.tar.gz`) so that the data files never go into git history.
`scripts/publish-data.ps1` exports the data, uploads the archive to that release, and starts
the workflow.
