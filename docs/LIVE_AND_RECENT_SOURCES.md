# Live and recent sources

NHTSA FARS, the only nationwide crash dataset, is published about 1.5 years after the year ends. Everything newer comes from local sources, which come in two kinds. The app keeps them apart everywhere, because they mean different things.

| Kind | What it is | Typical delay | Has injury counts? | Table |
|---|---|---|---|---|
| **Police crash report** | A filed report of a crash | about 1 day to a few weeks | yes | `nyc_crashes`, `local_crashes` |
| **Live incident** | A first report from 911 dispatch or a traffic-management system | minutes | no; unverified, some turn out minor | `live_incidents` |

## In the app now (checked Nov 15–16, 2026)

| Source | Kind | Covers | Delay seen | History loaded | Module |
|---|---|---|---|---|---|
| NYC Motor Vehicle Collisions (h9gi-nx95) | report | New York City | about 3 days | July 2012 → | `pipeline/nyc.py` |
| Chicago Traffic Crashes (85ca-t3if) | report | Chicago (police-handled crashes; interstates are mostly missing) | about 1 day | 2013 →, but complete only from Sept 2017 | `pipeline/chicago.py` |
| Austin-Travis County Real-Time Traffic Incidents (dx9v-zd7x) | live | Austin & Travis County | 30–60 min | Sept 2017 → | `pipeline/live/austin.py` |
| California Highway Patrol CAD (`sa.xml`) | live | California, roads CHP patrols | minutes | from first poll (active incidents only) | `pipeline/live/chp.py` |
| 511NJ / TRANSCOM active incidents RSS | live | New Jersey + New York region | minutes | from first poll | `pipeline/live/nj511.py` |
| WSDOT highway alerts (KML + RSS) | live | Washington state highways | about 15 min | from first poll | `pipeline/live/wsdot.py` |
| Seattle Real Time Fire 911 (kzjm-xkqj) | live | Seattle; vehicle-related call types only | about 15 min | 2003 → (84,144 calls) | `pipeline/live/seattle.py` |
| SF police dispatched calls, real-time (gnap-fj3t) | live | San Francisco; accident and traffic-hazard codes | 25 min to 2 h | rolling 48 h window, kept from first poll | `pipeline/live/sf.py` |

### Notes on each source

- **Snapshot feeds** (CHP, 511NJ, WSDOT) list only incidents that are currently active. The poller marks an incident `cleared` once it stops appearing, and never deletes it, so history builds up from the first poll. Polling every 10 minutes can miss incidents that clear faster than that.
- **511NJ** has no incident ID. The adapter uses the agency's CAD number when the description includes one, and otherwise a hash of the title, location and start time. If an agency edits the start time, the same incident can appear twice in history.
- **WSDOT's** RSS feed gives only a last-updated time, so `reported_at` moves when an alert is edited.
- **Seattle** includes "Rescue Extrication" and "Rescue Automobile" as crashes. Rarely, these may be other entrapments.
- **SF** coordinates are the nearest intersection, not the exact spot.
- **Pacific times** are converted to UTC with one shared helper (`pipeline/live/base.py`, backed by `tzdata`).

### Terms

- **Confirmed public domain or no restriction found:** Seattle, SF (PDDL), NYC, Austin and WSDOT.
- **Not yet confirmed:** CHP, 511NJ and Chicago. Check these before a public deploy.

## Candidates for the next batch (researched Nov 15, 2026, not built yet)

Police crash-report datasets with coordinates and an API, current to within about 60 days:

| Source | API | Newest record | Notes |
|---|---|---|---|
| **Iowa (statewide)** | ArcGIS `gis.iowadot.gov/.../Crash_Data/FeatureServer/0` | Nov 12, 2026 | 641k rows from 2015; 2,000 records per request |
| **Utah (statewide)** | ArcGIS `Utah_Crash_Locations/FeatureServer/0–7` | Nov 11, 2026 | one layer per year, 2019–2026 |
| Washington DC | ArcGIS `DCGIS_DATA/Public_Safety_WebMercator/MapServer/24` | Nov 13, 2026 | junk dates back to 1825; filter to ≥ 2000 |
| Nashville | ArcGIS `Traffic_Accidents_2/FeatureServer/0` | Nov 14, 2026 | from 2019 |
| Baton Rouge | Socrata `data.brla.gov` 7wah-qncc | Nov 14, 2026 | public domain |
| Johns Creek, GA | Socrata gezc-jm4k | Nov 14, 2026 | |
| Tucson | ArcGIS, one service per year 2018–2026 | Nov 13, 2026 | |
| Denver | ArcGIS `ODC_CRIME_TRAFFICACCIDENTS5YR_P/FeatureServer/325` | Nov 11, 2026 | offense rows; dedupe by incident_id |
| Montgomery County, MD | Socrata bhju-22kf | Nov 11, 2026 | public domain |
| Colorado Springs | Socrata bjpt-tkzq | Nov 11, 2026 | one row per vehicle/person; dedupe |
| Cincinnati | Socrata 7iz8-ecuw | Nov 11, 2026 | one row per person; dedupe |
| Seattle SDOT collisions | ArcGIS `SDOT_Collisions_All_Years_1/FeatureServer/0` | Nov 7, 2026 | filed reports; complements the 911 feed |
| Austin crash records (TxDOT CRIS) | Socrata y2wy-tgr5 | Oct 30, 2026 | filed reports; complements the live feed |
| Cambridge, MA / Somerville, MA | Socrata gb5w-yva3 / mtik-28va | Oct 2026 | small; Somerville is ODbL |

- **Skipped:**
  - Maryland statewide (needs a login)
  - Delaware (about 6 months behind)
  - LAPD (stopped updating in 2025)
  - North Carolina (no coordinates)
- **States with free-key live 511 feeds,** not built because they need someone to register:
  - Arizona, Georgia and Pennsylvania (same "511 v2" API)
  - New York (511NY)
  - Ohio (OHGO)
  - Minnesota (Castle Rock CARS)

Most of the candidates are Socrata or ArcGIS FeatureServer datasets. A single loader driven by a per-source field mapping would cover them better than one module each.
