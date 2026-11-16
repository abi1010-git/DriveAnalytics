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

## Crash-record portals in the app (43 sources)

Each is a module in `backend/pipeline/records/sources/` (this table is generated from them). Every module's docstring records what was verified against the live service: row counts, date range, id strategy, time convention and terms.

| Source | State | Platform | Notes |
|---|---|---|---|
| Allegheny County, PA crash reports (PennDOT via WPRDC) (`allegheny`) | PA | ckan | Month precision only (PennDOT withholds the crash date): crash_datetime is the 1st of the month. Published annually; always reloaded in full. CC0. |
| Austin, TX crash reports (TxDOT CRIS) (`austin_crashes`) | TX | socrata | Filed CRIS crash reports (lag ~2 weeks); distinct from the live 'austin' incident feed. |
| Baton Rouge, LA crash reports (`baton_rouge`) | LA | socrata | Date only (no crash time); severity from fatality/injury flags; no injury counts. |
| California CHP crash reports (CCRS, statewide) (`california`) | CA | ckan | Statewide from 2021, one CKAN resource per year (add each new year's Crashes resource). The newest weeks fill in as reports arrive, so recent counts are incomplete; ~23% of crashes have no coordinates; no severity label. |
| Cambridge, MA police crash reports (`cambridge_ma`) | MA | socrata | No crash id (built from time and address); severity from the first two persons only; PDDL. |
| Charlotte, NC (CDOT) crash reports (`charlotte`) | NC | arcgis | From 2019. Severity level and crash type only; no injury counts. Since Sep 2026 nearly all rows have broken coordinates at the source and are stored without a location. Nov-Dec 2025 mostly missing. |
| Cincinnati, OH crash reports (`cincinnati`) | OH | socrata | Per-person rows reduced to one crash; injured/killed counted from the persons listed. |
| Cleveland, OH crash reports (ODOT) (`cleveland`) | OH | arcgis | 2019-2025, closed dataset (no 2026). Hour precision: the time is the hour of the crash. |
| Colorado Springs, CO crash reports (`colorado_springs`) | CO | socrata | Severity composed from injury/death flags; no license stated on the portal. |
| Connecticut Crash Data Repository (Connecticut) (`connecticut`) | CT | arcgis | TERMS NOT CONFIRMED: dashboard backend of the UConn CT Crash Data Repository, not a documented open-data API; check CTCDR terms before sharing. Loaded from 2019 (about 768k crashes; the service goes back to 2015). Recent months fill in late. No injury or death counts. |
| Dallas County, TX crash reports (2025 only) (`dallas_county`) | TX | arcgis | TxDOT CRIS crashes in Dallas County for 2025 only (static). Deaths not counted: killed is 0 for non-fatal crashes and empty for fatal ones. |
| Washington, DC crash reports (`dc`) | DC | arcgis | Injury and death counts per road-user mode; no severity label. Date only before ~2015. |
| Delaware statewide crash reports (`delaware`) | DE | socrata | Statewide, about six months behind; no crash id (built from time and point); from 2019 on. |
| Denver, CO police traffic accident reports (`denver`) | CO | arcgis | Serious injuries only; severity is the offense label. Dataset to be replaced by end of Q4 2026. |
| Gainesville, FL police crash reports (60+ days delayed) (`gainesville`) | FL | socrata | Published at least 60 days after the crash (FL 316.066). Deaths only; no injury counts. |
| Greenville-Pickens, SC area (GPATS) crash reports, 2021-2025 (`greenville_sc`) | SC | arcgis | Static 2017-2025 export, loaded from 2021 (MPO boundary change). Terms unconfirmed (contact GPATS). Layer uses FID, so OBJECTID ordering in base.fetch fails. |
| Hawaii fatal crashes (`hawaii_fatal`) | HI | socrata | Fatal crashes only, from 2019 (earlier rows are yearly totals or placeholder dates). Date only, no time of day; no injury counts, weather or lighting. |
| Ada & Canyon counties, ID crash reports (COMPASS) (`idaho_compass`) | ID | arcgis | Ada and Canyon counties only (Boise/Nampa area), from 2019 through the last published year (2025 when checked). No cause or collision-type fields. |
| Illinois DOT crash reports (`illinois`) | IL | arcgis | Statewide 2021-2025 (about 1.5M crashes), published yearly after the year closes; add each new CrashExtract<year> service to urls. Street names only from 2025. |
| Iowa DOT crash reports (`iowa`) | IA | arcgis | Statewide from 2015 (about 641k crashes). No hit-and-run field. |
| Johns Creek, GA police crash reports (`johns_creek`) | GA | socrata | No severity or injury counts; no license stated by the publisher. |
| Kansas DOT crash reports (statewide, from 2019) (`kansas`) | KS | arcgis | Statewide, bounded to 2019 onward (the service goes back to 2016). Reports arrive months late, so recent months are far from complete. Time of day is the hour only; no road names or hit-and-run flag. |
| Knoxville, TN region (Knoxville TPO area) crash reports (`knoxville`) | TN | arcgis | No crash id published: source_id is derived from date/time, coordinates and crash fields (~0.03% merged; corrections upstream create duplicates). Recent rows are often date-only. |
| MaineDOT crash reports (Maine) (`maine`) | ME | arcgis | Statewide rolling 10 years plus current year (about 361k crashes from 2016), refreshed weekly. The service is a view named '..._Test_View' and may be renamed; no hit-and-run field. |
| MassDOT crash reports (Massachusetts) (`massachusetts`) | MA | arcgis | Statewide from 2021 (about 767k crashes), one service per year; add the next year's MASSDOT_ODP_OPEN_<year> to YEARS each January (2023's is named 2023v). Current and previous year rows are preliminary (CRASH_STATUS Open). About 5% of crashes have no coordinates. |
| Mesa County, CO crash reports (`mesa_county`) | CO | arcgis | Mesa County (Grand Junction area) only, 2018 through 2025; the service is named per year, so a newer year needs a new url. Hit-and-run flags are mostly empty before 2025. |
| Montana DOT crash reports (statewide, 2021-2025) (`montana`) | MT | arcgis | Statewide from 2021 through the last published year (2025 when checked); date only. No crash id is published, so ids are built from date, position, route and collision type (0.14% of rows collapse). Severity label only, no injury or death counts. |
| Montgomery County, MD crash reports (`montgomery_md`) | MD | socrata | Severity is a report type only; no injury counts. |
| Nashville (Davidson County), TN crash reports (`nashville`) | TN | arcgis | From 2019; injury and death counts but no severity label. |
| North Carolina fatal & serious-injury crashes only (2016-2025) (`nc_serious`) | NC | arcgis | Fatal (K) and serious-injury (A) crashes only, statewide, rolling 10 years updated annually. Date is text: incremental filters match nothing, use full reloads. Layer uses FID (OBJECTID ordering fails). |
| Ohio DOT crash locations (`ohio`) | OH | arcgis | Month precision only (crash_datetime = 1st of the month, 00:00). No injury counts or road names. No date field, so incremental updates fail: reload yearly with full=True. |
| Oregon fatal crashes (preliminary) (`oregon_fatal`) | OR | arcgis | Fatal crashes only, from ODOT's preliminary initial reports; covers the current and previous year. No injury counts, weather or lighting. |
| Raleigh, NC police crash reports (`raleigh`) | NC | arcgis | Raleigh PD reports, essentially 2015 onward. No severity label; injured = type A+B+C. Misuse may be prosecuted under NC GS 14-117. |
| San José, CA DOT crash reports (`san_jose`) | CA | arcgis | From 2019. Also covered by California's statewide CCRS source (kept separately). Recent months fill in slowly. |
| Seattle SDOT collision reports (`seattle_sdot`) | WA | arcgis | Filed reports from 2003, added with a lag of days to weeks; distinct from the live 'seattle' 911 feed. |
| Southeast Michigan (SEMCOG) crash reports (`semcog`) | MI | arcgis | Seven SE Michigan counties, 2021-2025. Requires the SEMCOG copyright notice wherever shown (licence allows redistribution). No date field: reload with full=True. |
| Somerville, MA police crash reports (`somerville_ma`) | MA | socrata | About one month delay; no state roads. ODbL: attribution and share-alike required. |
| St. Louis County, MO police crash reports (`st_louis_county`) | MO | arcgis | From 2021. Injury and death counts only; no severity label, cause or conditions. Rows without a crash id (Accident_ID 0) are skipped. |
| Tucson, AZ police collision reports (`tucson`) | AZ | arcgis | City of Tucson (TPD) only, from 2018; time to the hour; one service per year. |
| Utah DOT crash reports (`utah`) | UT | arcgis | Statewide from 2019, one service layer per year; a new year's layer must be added to `urls`. No primary-cause field. |
| VTrans crash reports (Vermont) (`vermont`) | VT | arcgis | Statewide from 2010 (about 183k crashes). Severity is a crash type only (Fatal/Injury/Property Damage Only); no injury or death counts, no lighting or hit-and-run field. |
| Virginia DOT crash reports (`virginia`) | VA | arcgis | Statewide from 2019-01-01 (the service goes back to 2017; about 916k crashes loaded). Published about 2.5 months behind. No primary-cause field. |
| Wichita, KS police traffic accident reports (`wichita`) | KS | arcgis | From 2021. Offense type only: no injury or death counts or severity. Kansas statewide (KDOT) data also covers Wichita. |

### Terms to settle before a public deploy
- **Connecticut** (UConn dashboard backend) and **Minnesota** (statewide layer published by an individual account; not loaded): terms unconfirmed.
- **SEMCOG:** its license grants reuse but the required notice says "Reproduction or Use Without Permission is Prohibited"; clarify with SEMCOG.
- **Somerville:** ODbL (attribution + share-alike for a published derived database).
- **Raleigh:** carries an NC GS 14-117 misuse warning.
- Several portals state no license at all (listed in each module's docstring).

### States with no usable no-key per-crash source (Nov 2026 survey)
NH, RI, WV, NJ (statewide records behind bot protection), IN, WI (bulk access forbidden), KY, MN (login), WA statewide records, NV, AZ statewide, ID statewide, CO statewide, NM, NE, WY, ND, SD, AK, and most of the South statewide (FL, GA, SC, AL, MS, AR, OK, MO, LA, TX). Cities and regions inside some of these are covered above.
