"""Cambridge, MA Police "Crash Data - Updated" (Socrata gb5w-yva3).

Checked Nov 2026: 17,395 rows, one per crash, 2015-01-01 to 2026-10-31, updated quarterly.
License: Open Data Commons PDDL (public domain dedication), attribution "City of Cambridge
Public Safety" requested.

Ids: the dataset has no crash or report number, so source_id is built from the fields that
place a crash: date_time + street_number + street_name + cross_street (whitespace collapsed,
upper case), as "<date_time>-<sha1 prefix>". Location is left out because a re-geocode
would change the id. Risk: 8 rows (0.05%) share a key with another crash at the same minute
and address and collapse into one; if the city edits any of these four fields in a later
release, the crash gets a new id and the old row stays behind as a duplicate.

Coordinates: the `location` point; only ~9k rows carry latitude/longitude (others have just
an address or nothing). Severity is the most severe of p1_injury/p2_injury, in the city's
own words (older rows use "NON FATAL INJURY - ..." labels, newer ones KABCO wording). Only
the first two persons are published, so severity can understate a crash and injury/death
counts stay empty. hit_and_run is True when either vehicle's flag is "Y"; the flag is
otherwise blank, so it stays None rather than False. date_time is a floating local timestamp.
"""
import hashlib

from ..base import SourceSpec, floating, point, sane, text

# Most to least severe; both the old "NON FATAL INJURY" and the KABCO labels the city uses.
INJURY_RANK = {
    "FATAL INJURY": 5,
    "SUSPECTED SERIOUS INJURY": 4, "NON FATAL INJURY - INCAPACITATING": 4,
    "SUSPECTED MINOR INJURY": 3, "NON FATAL INJURY - NON INCAPACITATING": 3,
    "POSSIBLE INJURY": 2, "NON FATAL INJURY - POSSIBLE": 2,
    "NO APPARENT INJURY": 1, "NO INJURY": 1,
}


def _norm(value) -> str:
    return (text(value) or "").upper()


def crash_id(raw: dict) -> str | None:
    when = text(raw.get("date_time"))
    if not when:
        return None
    key = "|".join([when, *(_norm(raw.get(f)) for f in ("street_number", "street_name", "cross_street"))])
    return f"{when[:16]}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"


def severity(raw: dict) -> str | None:
    labels = [_norm(raw.get(f)) for f in ("p1_injury", "p2_injury")]
    ranked = [label for label in labels if label in INJURY_RANK]
    return max(ranked, key=INJURY_RANK.get) if ranked else None


def parse(raw: dict) -> dict | None:
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    lat, lon = point(SPEC, location.get("latitude"), location.get("longitude"))
    street, cross = text(raw.get("street_name")), text(raw.get("cross_street"))
    return {
        "source_id": crash_id(raw),
        "crash_datetime": sane(floating(raw.get("date_time"))),
        "latitude": lat,
        "longitude": lon,
        "road": f"{street} & {cross}" if street and cross else street or cross,
        "injured": None,
        "killed": None,
        "severity": severity(raw),
        "primary_cause": None,
        "weather": text(raw.get("weather_condition_1")),
        "lighting": text(raw.get("ambient_light")),
        "crash_type": text(raw.get("manner_of_collision")),
        "hit_and_run": True if "Y" in (raw.get("v1_hit_and_run"), raw.get("v2_hit_and_run")) else None,
    }


SPEC = SourceSpec(
    source="cambridge_ma",
    label="Cambridge, MA police crash reports",
    platform="socrata",
    url="https://data.cambridgema.gov/resource/gb5w-yva3.json",
    date_field="date_time",
    parse=parse,
    states=[25],
    bbox=(-71.2, 42.33, -71.04, 42.42),
    tz="America/New_York",
    page_size=50000,
    notes="No crash id (built from time and address); severity from the first two persons only; PDDL.",
)
