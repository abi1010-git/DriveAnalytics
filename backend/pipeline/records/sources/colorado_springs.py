"""Colorado Springs, CO "Crash Data" (CSPD, Socrata bjpt-tkzq on policedata.coloradosprings.gov).

Checked Nov 2026: 100,066 rows, 100,008 distinct accidentnumber, 2016-01-01 to 2026-11-11.
Rows are per crash (the at-fault driver's details are attached); the 58 repeated numbers
have identical crash-level fields (time, counts, location), so the loader keeping the last row
is enough and no `reduce` is needed. The portal states no license (description: "all traffic
crashes reported to CSPD").

accidentdatetime is a floating local timestamp (hour profile peaks 15-17h). Coordinates come
from location_point (GeoJSON [lon, lat]); ~5.7k rows have none and ~70 geocode outside the
area and are dropped by the bbox. injured/killed are numberofinjured/numberofkilled. There is
no severity label, so it is composed from the source's flags: involved_death_="Yes" -> "Fatal",
else involved_injury_="Yes" -> "Injury", else both "No" -> "No injury". primary_cause is the
at-fault driver's driveraction; crash_type is firstharmfulevent. No weather or lighting.
"""
from ..base import SourceSpec, floating, number, point, sane, text

_YES_NO = {"Yes": True, "No": False}


def _severity(raw: dict) -> str | None:
    death, injury = _YES_NO.get(raw.get("involved_death_")), _YES_NO.get(raw.get("involved_injury_"))
    if death:
        return "Fatal"
    if injury:
        return "Injury"
    if death is False and injury is False:
        return "No injury"
    return None


def parse(raw: dict) -> dict | None:
    coords = (raw.get("location_point") or {}).get("coordinates") or [None, None]
    lat, lon = point(SPEC, coords[1], coords[0]) if len(coords) >= 2 else (None, None)
    return {
        "source_id": text(raw.get("accidentnumber")),
        "crash_datetime": sane(floating(raw.get("accidentdatetime"))),
        "latitude": lat,
        "longitude": lon,
        "road": text(raw.get("streetaddress")),
        "injured": number(raw.get("numberofinjured")),
        "killed": number(raw.get("numberofkilled")),
        "severity": _severity(raw),
        "primary_cause": text(raw.get("driveraction")),
        "weather": None,
        "lighting": None,
        "crash_type": text(raw.get("firstharmfulevent")),
        "hit_and_run": None,
    }


SPEC = SourceSpec(
    source="colorado_springs",
    label="Colorado Springs, CO crash reports",
    platform="socrata",
    url="https://policedata.coloradosprings.gov/resource/bjpt-tkzq.json",
    date_field="accidentdatetime",
    parse=parse,
    states=[8],
    bbox=(-105.05, 38.65, -104.55, 39.15),
    tz="America/Denver",
    page_size=50000,
    notes="Severity composed from injury/death flags; no license stated on the portal.",
)
