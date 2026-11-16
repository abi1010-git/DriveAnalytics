"""Wichita Police Department "Traffic Accidents" (ArcGIS OpenData/TrafficAccidents/FeatureServer).

Checked Nov 2026 against the live service. Layers: 0 = 2018, 1 = 2019, 2 = 2020, 3 = 2021,
4 = "Traffic Accidents All", 5 = 2022, 6 = 2023, 7 = 2024, 8 = 2025, 9 = 2026 (not in id
order). This source reads layer 4 ("All", 99,735 rows from 2018-01-01 to 2026-11-14) bounded to
2021+ (65,303 rows) instead of the per-year layers, because the year layers are unreliable:
the 2025 layer stops at 2025-12-01 (18 December rows against 793 in "All"), and several year
layers hold rows from other years (the "2024" layer starts in Feb 2021, "2023" in Apr 2022).
"All" holds the current 2026 rows too (same newest row as layer 9). No license is stated.

Rows are per OFFENSE: one INCIDENTID can appear several times with different offense codes
(or different address strings), e.g. "MOTOR VEHICLE/MOTOR VEHICLE IN TRANSPORT" plus
"MOTOR VEHICLE/FIXED OBJECT". `reduce` merges them: crash_type lists the distinct offense
labels, hit_and_run is True if any label says HIT AND RUN (otherwise unknown).

Time: ACCIDENT_DATE stores local wall time as if it were UTC (epoch_is_local=True). Of 8,000
rows since June 2025, the published weekday (DOWFULL) matches the stored value read as-is in
all 8,000 and only 7,502 when converted from UTC to Central time; the hour profile as stored
peaks at 15-17 h and is lowest at 3-4 h; and every year layer starts just after 00:00.

Fields: there are no injury, death or severity fields (offense code/label only), so injured,
killed and severity stay None. road is LOCATION (a street or block address).
"""
from ..base import SourceSpec, epoch, point, sane, text


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    label = text(raw.get("OFFENSE_DE"))
    return {
        "source_id": text(raw.get("INCIDENTID")),
        "crash_datetime": sane(epoch(SPEC, raw.get("ACCIDENT_DATE")), earliest=2021),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("LOCATION")),
        "injured": None,
        "killed": None,
        "severity": None,
        "primary_cause": None,
        "weather": None,
        "lighting": None,
        "crash_type": label,
        "hit_and_run": True if label and "HIT AND RUN" in label else None,
    }


def reduce(rows: list[dict]) -> dict:
    """Offense rows of one incident: keep the first value present per column, list every
    distinct offense label, and keep hit_and_run if any offense says so."""
    merged = dict(rows[0])
    for key in merged:
        if merged[key] is None:
            merged[key] = next((r[key] for r in rows if r.get(key) is not None), None)
    labels = list(dict.fromkeys(r["crash_type"] for r in rows if r.get("crash_type")))
    merged["crash_type"] = "; ".join(labels) or None
    merged["hit_and_run"] = True if any(r.get("hit_and_run") for r in rows) else None
    return merged


SPEC = SourceSpec(
    source="wichita",
    label="Wichita, KS police traffic accident reports",
    platform="arcgis",
    url="https://gismaps.wichita.gov/ageweb/rest/services/OpenData/TrafficAccidents/FeatureServer/4",
    date_field="ACCIDENT_DATE",
    parse=parse,
    states=[20],
    bbox=(-97.62, 37.48, -97.10, 37.86),
    tz="America/Chicago",
    where="ACCIDENT_DATE >= TIMESTAMP '2021-01-01 00:00:00'",
    page_size=2000,
    epoch_is_local=True,
    reduce=reduce,
    notes="From 2021. Offense type only: no injury or death counts or severity. Kansas statewide "
          "(KDOT) data also covers Wichita.",
)
