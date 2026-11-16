"""San José DOT "Crash Locations" (ArcGIS MapServer OPN/OPN_OpenDataService/512).

Checked Nov 2026 against the live service: 608,905 rows ("all crashes known to the City
since 1977"), 35,856 from 2019 (2019: 5,397; 2020: 4,339; 2021: 4,707; 2022: 5,149; 2023:
4,540; 2024: 5,623; 2025: 4,665; 2026: 1,436 so far - recent months lag, mostly injury
crashes arrive first). Newest crash 2026-11-08 17:44 local. Owner "City of San Jose"; no
license is stated on the layer.

Rows are per CRASH, not per vehicle: vehicle details are aggregated into text lists
("Driver, Driver") with a VEHICLECOUNT, and the per-vehicle data is a separate related
dataset. TCRNUMBER is unique and never null from 2019 (group-by/having check). `reduce` is a
safeguard in case a crash ever repeats: it takes the crash-level counts once (max), never a
sum.

Overlap: California's statewide CCRS source also covers San José. This is the city's own
DOT copy with a different source id, so the two are not merged.

Time: CRASHDATETIME stores local wall time as if it were UTC (epoch_is_local=True). The
layer also has CRASHDATETIMEUTC, which is exactly 8 h later in winter and 7 h later in summer
(1794159840000 vs 1794188640000 on 2026-11-08; 1792738980000 vs 1792764180000 on
2026-10-23), and HOUR matches CRASHDATETIME read as local (17 for 17:44).

Fields: injured = MINORINJURIES + MODERATEINJURIES + SEVEREINJURIES, killed = FATALINJURIES;
severity = INJURYSEVERITY (e.g. "Fatal, Severe, Minor"; empty for property-damage crashes).
NARRATIVE and AGERANGE describe the people involved (ages, sex) and are deliberately not stored.
"""
from ..base import SourceSpec, epoch, number, point, sane, text

INJURY_COUNTS = ("MINORINJURIES", "MODERATEINJURIES", "SEVEREINJURIES")


def _injured(raw: dict) -> int | None:
    counts = [number(raw.get(k)) for k in INJURY_COUNTS]
    return None if all(c is None for c in counts) else sum(c or 0 for c in counts)


def parse(raw: dict) -> dict | None:
    lat, lon = point(SPEC, raw.get("LATITUDE"), raw.get("LONGITUDE"))
    if lat is None:
        lat, lon = point(SPEC, raw.get("_lat"), raw.get("_lon"))
    return {
        "source_id": text(raw.get("TCRNUMBER")),
        "crash_datetime": sane(epoch(SPEC, raw.get("CRASHDATETIME")), earliest=2019),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("INTASTREETNAME")),
        "injured": _injured(raw),
        "killed": number(raw.get("FATALINJURIES")),
        "severity": text(raw.get("INJURYSEVERITY")),
        "primary_cause": text(raw.get("PRIMARYCOLLISIONFACTOR")),
        "weather": text(raw.get("WEATHER")),
        "lighting": text(raw.get("LIGHTING")),
        "crash_type": text(raw.get("COLLISIONTYPE")),
        "hit_and_run": {"True": True, "False": False}.get(raw.get("HITANDRUNFLAG")),
    }


def reduce(rows: list[dict]) -> dict:
    """Repeated rows of one crash carry crash-level counts: take them once (max), never sum."""
    merged = dict(rows[0])
    for key in merged:
        if merged[key] is None:
            merged[key] = next((r[key] for r in rows if r.get(key) is not None), None)
    for key in ("injured", "killed"):
        counts = [r[key] for r in rows if r.get(key) is not None]
        merged[key] = max(counts) if counts else None
    return merged


SPEC = SourceSpec(
    source="san_jose",
    label="San José, CA DOT crash reports",
    platform="arcgis",
    url="https://geo.sanjoseca.gov/server/rest/services/OPN/OPN_OpenDataService/MapServer/512",
    date_field="CRASHDATETIME",
    parse=parse,
    states=[6],
    bbox=(-122.06, 37.12, -121.58, 37.48),
    tz="America/Los_Angeles",
    where="CRASHDATETIME >= TIMESTAMP '2019-01-01 00:00:00'",
    page_size=1000,  # the server is slow under load: a 2000-row page once exceeded the 120 s read timeout
    epoch_is_local=True,
    reduce=reduce,
    notes="From 2019. Also covered by California's statewide CCRS source (kept separately). "
          "Recent months fill in slowly.",
)
