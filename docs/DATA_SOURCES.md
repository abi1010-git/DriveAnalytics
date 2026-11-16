# Data sources

DriveAnalytics uses two public datasets. Each is loaded by its own module in `backend/pipeline/`, because their coverage and fields are too different to merge into one table honestly.

| | NHTSA FARS | NYC Motor Vehicle Collisions |
|---|---|---|
| Covers | Every crash on a US public road in which someone died within 30 days | Every police-reported crash in New York City (MV-104AN form) |
| Years | 1975 onward; this project loads 2020–2024 by default | July 2012 to present, updated daily |
| Size | About 35–40k crashes a year | About 2.3 million crashes |
| Location | Latitude/longitude for almost every crash | Latitude/longitude for about 90% of crashes |
| "Why" fields | Coded speeding, drinking, weather, lighting, junction, road type | Up to five free-text contributing factors per crash |
| Publisher | National Highway Traffic Safety Administration | NYPD, via NYC Open Data |
| Module | `pipeline/fars.py` | `pipeline/nyc.py` |

## NHTSA FARS

- **Download:** one zip per year at `https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/FARS{year}NationalCSV.zip` (about 31–35 MB each for 2020–2024).
- **Files used:**
  - `accident.csv`: one row per crash.
  - `vehicle.csv`: one row per vehicle. Speeding, drinking and the speed limit are recorded per vehicle, so the loader rolls them up per crash.
- **Checked against the 2020 and 2024 files, not taken from memory:**
  - Every code column has a `*NAME` label column next to it, for example `WEATHER` and `WEATHERNAME`. We store the label, so no lookup tables are needed.
  - Unknown coordinates use repeated-digit codes: latitude `77.7777`, `88.8888` or `99.9999`, and longitude `777.7777`, `888.8888` or `999.9999`. The loader stores these as NULL.
  - Hour `99`, minute `99` and day `99` mean unknown, and are stored as NULL too.
  - `SPEEDREL` 2–5 means speeding of some kind:
    - 2 = racing
    - 3 = over the limit
    - 4 = too fast for conditions
    - 5 = speeding, details unknown

    Codes 8 and 9 (no driver present, unknown) don't count as speeding.
  - `DR_DRINK = 1` means police reported the driver as drinking. This is not a test result.
  - `VSPD_LIM`: 0 = no statutory limit, 98 = not reported, 99 = unknown. The loader ignores all three.
  - Most years are ASCII, but some contain Windows-1252 characters. 2020 has "LA CAÑADA FLINTRIDGE", for example. The loader tries UTF-8 first and falls back to cp1252.
  - `ST_CASE` is unique only within a year, so crash IDs are stored as `"{year}-{ST_CASE}"`.
  - City and county names include placeholders: "Other", "Not Reported" and "Unknown", with letter case varying by year. These are stored as NULL so they don't show up as a "city" called Other.
  - Road names (`TWAY_ID`) are free text written differently by each state. Examples: "I-45/GULF FWY", "SR-3 GRATIOT AVE", "FM 1093/WESTHEIMER RD", and "MU-COIT RD", where MU- marks a municipal street. The loader derives `road_route`:
    - a leading route number wins, so these become `I-45`, `SR-3` and `FM-1093`
    - otherwise it takes the name before any "/" alias, with a road-class prefix such as "MU-" removed

    This is what roads are ranked by.
- **Re-running** a year replaces that year in a single transaction, so running it twice gives the same result.

## NYC Open Data: Motor Vehicle Collisions – Crashes (`h9gi-nx95`)

- **API:** `https://data.cityofnewyork.us/resource/h9gi-nx95.json` (Socrata SODA). The loader:
  - pages with `$order=collision_id` and `collision_id > last_seen`, 50,000 rows at a time, instead of `$offset`. Offset paging slows down the deeper it goes and can skip or repeat rows if the data changes during a download.
  - handles incremental updates with `--since YYYY-MM-DD`, which filters on the system field `:updated_at`. That catches old crashes NYPD amended later, not just new ones.
- **Raw cache:** rows are saved to `backend/data/raw/nyc/*.jsonl.gz` before loading, so a schema or rule change can be re-loaded without downloading again.
- **Checked against the live API (Nov 2026):**
  - `crash_date` is a midnight timestamp, and `crash_time` is `H:MM` text.
  - Numbers arrive as strings, and empty fields are left out of the JSON entirely.
  - `vehicle_type_code1`/`2` have no underscore; `vehicle_type_code_3`/`4`/`5` do.
  - `off_street_name` holds a street address and `cross_street_name` a cross street. The dataset's own column descriptions have these two swapped, but the data matches the field names.
- **Cleaning:**
  - Coordinates outside a box around the five boroughs (lat 40.45–40.95, lon −74.30 to −73.65) are stored as NULL. This removes the 0/0 points and impossible values such as longitude −201.36.
  - The factor "Does Not Apply" is dropped, because it means there was no such vehicle. "Unspecified" is kept, because it means police didn't say.
  - Spelling variants of the same factor are merged ("Illnes" → "Illness", "Drugs (illegal)" → "Drugs (Illegal)", …). Bare numbers such as "80" are dropped as data-entry errors.
- **Re-running** inserts new crashes and updates existing ones in place. A crash's factors and flags are replaced along with it.

## Limits worth knowing

- FARS includes only fatal crashes. It shows where people died, not where crashes happen most often.
- NYC data is "preliminary and subject to change" according to the publisher. Contributing factors are an officer's judgment at the scene.
- Neither dataset has traffic volume, so raw counts favor busy roads. Phase 2 will rank by severity and say clearly what the ranking can't tell you.
