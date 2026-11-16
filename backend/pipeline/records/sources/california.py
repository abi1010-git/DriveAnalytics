"""CHP California Crash Reporting System (CCRS) "Crashes" tables on data.ca.gov (CKAN, package
"ccrs"), statewide, one datastore resource per year; 2021-2026 are loaded.

Checked Nov 2026 through datastore_search_sql: one row per crash, "Collision Id" unique in
every year and never repeated across the six year resources (a UNION check found 0 shared
ids), so keyset paging on it is stable. Rows: 2026: 321,356 (to 2026-11-14 17:22); 2025:
402,516; 2024: 417,173; 2023: 409,836; 2022: 405,239; 2021: 422,983. About 23% of rows have
no Latitude/Longitude (73,120 in 2026). "IsDeleted" was "False" on every row, but the filter
stays in case deleted reports are ever published. A few hundred rows per year are
"Is Preliminary" = "True"; they are kept (the row is replaced when the final report lands).
The server caps one SQL response at 32,000 rows; pages of 5,000 keep responses small, since
SELECT * also returns CKAN's _full_text column.

Reporting lag: the newest weeks fill in as reports arrive (Nov 2026: ~850 crashes a day in
mid-October, ~600 on Nov 3, ~100 on Nov 11, 9 on Nov 14), so updates re-read 45 days instead
of the default 3, and recent counts are always incomplete.

Time: "Crash Date Time" is a timestamp without zone holding Pacific wall time (it matches the
"Crash Time Description" text, e.g. 03:32 / "0332"), so it is used as is.

Fields: injured = NumberInjured, killed = NumberKilled. There is no severity label in the
table, so severity stays empty rather than being derived from the counts. primary_cause is
"Primary Collision Factor Violation" (a Vehicle Code section, sometimes only the number, e.g.
"22350"). HitRun is "F" (felony) or "M" (misdemeanor) for hit-and-runs and empty otherwise;
empty is left as unknown rather than read as "no". road is PrimaryRoad, with SecondaryRoad
after " & " when given. A new year's Crashes resource must be added to RESOURCES.
License: "Other (Public Domain)".
"""
from datetime import timedelta

from ..base import SourceSpec, floating, number, point, sane, text

RESOURCES = {  # Crashes_<year> resource ids from package_show?id=ccrs
    2026: "b8ce0ca4-b4e9-490d-b4d1-1f4ec48cbefb",
    2025: "9f4fc839-122d-4595-a146-43bc4ed16f46",
    2024: "f775df59-b89b-4f82-bd3d-8807fa3a22a0",
    2023: "436642c0-cd04-4a4c-b45e-564b66437476",
    2022: "7828780b-117b-455e-9275-986ad3ffde50",
    2021: "d08692e2-6d36-487e-bca0-28cd127a626f",
}


def _road(raw: dict) -> str | None:
    primary, secondary = text(raw.get("PrimaryRoad")), text(raw.get("SecondaryRoad"))
    if primary and secondary:
        return f"{primary} & {secondary}"
    return primary or secondary


def parse(raw: dict) -> dict | None:
    if text(raw.get("IsDeleted")) == "True":
        return None
    collision_id = number(raw.get("Collision Id"))
    lat, lon = point(SPEC, raw.get("Latitude"), raw.get("Longitude"))
    hit_run = text(raw.get("HitRun"))
    return {
        "source_id": str(collision_id) if collision_id else None,
        "crash_datetime": sane(floating(raw.get("Crash Date Time"))),
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": number(raw.get("NumberInjured")),
        "killed": number(raw.get("NumberKilled")),
        "severity": None,
        "primary_cause": text(raw.get("Primary Collision Factor Violation")),
        "weather": text(raw.get("Weather 1")),
        "lighting": text(raw.get("LightingDescription")),
        "crash_type": text(raw.get("Collision Type Description")),
        "hit_and_run": True if hit_run in ("F", "M") else None,
    }


SPEC = SourceSpec(
    source="california",
    label="California CHP crash reports (CCRS, statewide)",
    platform="ckan",
    url="https://data.ca.gov/api/3/action/datastore_search_sql",
    urls=list(RESOURCES.values()),
    id_field="Collision Id",
    date_field="Crash Date Time",
    where="\"IsDeleted\" IS DISTINCT FROM 'True'",
    parse=parse,
    states=[6],
    bbox=(-124.5, 32.5, -114.1, 42.05),
    tz="America/Los_Angeles",
    page_size=5000,
    overlap=timedelta(days=45),
    notes="Statewide from 2021, one CKAN resource per year (add each new year's Crashes resource). "
          "The newest weeks fill in as reports arrive, so recent counts are incomplete; ~23% of crashes "
          "have no coordinates; no severity label.",
)
