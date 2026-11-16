"""Load NYC Open Data "Motor Vehicle Collisions - Crashes" (dataset h9gi-nx95).

Every police-reported crash in New York City since July 2012 (about 2.3M rows, updated
daily). We page through the public SODA API and save the raw rows as gzipped JSON lines,
then load that file. Keeping the two steps apart means a schema or rule change can be
re-loaded without downloading 2.3M rows again.

Facts checked against the live API (Nov 2026):
- crash_date is an ISO timestamp at midnight; crash_time is "H:MM" text.
- numbers arrive as strings; empty fields are left out of the JSON entirely.
- vehicle_type_code1/2 have no underscore, vehicle_type_code_3/4/5 do.
- off_street_name holds a street address and cross_street_name a cross street. The
  dataset's own column descriptions have these two swapped; the data matches the field names.
- about 10% of rows have no coordinates, and some have 0/0 or impossible longitudes.
"""
import gzip
import json
import re
import urllib.parse
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import CrashFlag, NycCrash, NycCrashFactor
from app.services.rule_engine import Rule, flag_ids

from .common import RAW_DIR, batched, bulk_insert, download, record_run, utcnow

DATASET_URL = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"
COUNT_FIELDS = {
    "persons_injured": "number_of_persons_injured", "persons_killed": "number_of_persons_killed",
    "pedestrians_injured": "number_of_pedestrians_injured", "pedestrians_killed": "number_of_pedestrians_killed",
    "cyclists_injured": "number_of_cyclist_injured", "cyclists_killed": "number_of_cyclist_killed",
    "motorists_injured": "number_of_motorist_injured", "motorists_killed": "number_of_motorist_killed",
}
FACTOR_FIELDS = [f"contributing_factor_vehicle_{i}" for i in range(1, 6)]
VEHICLE_FIELDS = ["vehicle_type_code1", "vehicle_type_code2", "vehicle_type_code_3", "vehicle_type_code_4", "vehicle_type_code_5"]
SELECT_FIELDS = ["collision_id", "crash_date", "crash_time", "borough", "zip_code", "latitude", "longitude",
                 "on_street_name", "cross_street_name", "off_street_name", *COUNT_FIELDS.values(), *FACTOR_FIELDS, *VEHICLE_FIELDS]
# A generous box around the five boroughs; anything outside it is a geocoding error.
NYC_BOUNDS = {"lat": (40.45, 40.95), "lon": (-74.30, -73.65)}
# "Does Not Apply" means there was no such vehicle or factor, so it is not stored.
IGNORED_FACTORS = {"does not apply", ""}
# NYPD's labels changed spelling over the years; merge variants of the same factor.
FACTOR_ALIASES = {
    "illnes": "Illness",
    "drugs (illegal)": "Drugs (Illegal)",
    "cell phone (hand-held)": "Cell Phone (Hand-Held)",
    "reaction to other uninvolved vehicle": "Reaction to Uninvolved Vehicle",
    "none": "Unspecified",
}
_SPACES = re.compile(r"\s+")


def raw_path(raw_dir: Path = RAW_DIR, since: str | None = None) -> Path:
    name = f"crashes_updated_since_{since}.jsonl.gz" if since else "crashes_full.jsonl.gz"
    return raw_dir / "nyc" / name


def page_url(after_id: str | None, limit: int, since: str | None) -> str:
    """Keyset paging on collision_id (the dataset's unique key) instead of $offset, which
    gets slower the deeper it goes and can skip or repeat rows if data changes mid-download."""
    where = []
    if after_id:
        where.append(f"collision_id > '{after_id}'")
    if since:
        where.append(f":updated_at >= '{since}T00:00:00'")
    params = {"$select": ",".join(SELECT_FIELDS), "$order": "collision_id", "$limit": str(limit)}
    if where:
        params["$where"] = " AND ".join(where)
    return f"{DATASET_URL}?{urllib.parse.urlencode(params)}"


def fetch(raw_dir: Path = RAW_DIR, since: str | None = None, page_size: int = 50000, force: bool = False,
          fetch_page=None, log=print) -> Path:
    """Download all rows (or rows updated on/after `since`, YYYY-MM-DD) to a gzipped JSON-lines file."""
    dest = raw_path(raw_dir, since)
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    fetch_page = fetch_page or _fetch_page
    part = dest.with_suffix(dest.suffix + ".part")
    after_id, total = None, 0
    with gzip.open(part, "wt", encoding="utf-8") as out:
        while True:
            rows = fetch_page(page_url(after_id, page_size, since))
            for row in rows:
                out.write(json.dumps(row) + "\n")
            total += len(rows)
            if rows:
                log(f"  nyc: {total:,} rows downloaded")
            if len(rows) < page_size:
                break
            after_id = rows[-1]["collision_id"]
    part.replace(dest)
    return dest


def _fetch_page(url: str) -> list[dict]:
    tmp = RAW_DIR / "nyc" / "_page.json"
    download(url, tmp, force=True)
    try:
        return json.loads(tmp.read_text(encoding="utf-8"))
    finally:
        tmp.unlink(missing_ok=True)


def iter_raw(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _clean(value) -> str | None:
    value = _SPACES.sub(" ", str(value or "")).strip()
    return value or None


def _count(value) -> int:
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return 0


def canonical_factor(value) -> str | None:
    label = _clean(value)
    if label is None or label.casefold() in IGNORED_FACTORS or label.isdigit():  # bare numbers are data-entry errors
        return None
    return FACTOR_ALIASES.get(label.casefold(), label)


def _coordinate(lat_raw, lon_raw) -> tuple[float | None, float | None]:
    try:
        lat, lon = float(lat_raw), float(lon_raw)
    except (TypeError, ValueError):
        return None, None
    (lat_min, lat_max), (lon_min, lon_max) = NYC_BOUNDS["lat"], NYC_BOUNDS["lon"]
    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
        return lat, lon
    return None, None


def parse_record(raw: dict) -> tuple[dict, list[dict]] | None:
    """Turn one API row into a crash dict and its factor rows. Returns None for rows that
    cannot be placed in time (no id or no date)."""
    collision_id = _clean(raw.get("collision_id"))
    crash_date = raw.get("crash_date")
    if not collision_id or not crash_date:
        return None
    try:
        day = datetime.fromisoformat(crash_date[:10])
    except ValueError:
        return None
    when, known_hour = day, None
    try:
        hour, minute = (int(part) for part in (raw.get("crash_time") or "").split(":")[:2])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            when, known_hour = day.replace(hour=hour, minute=minute), hour
    except ValueError:
        pass  # keep the date; the time is unknown
    lat, lon = _coordinate(raw.get("latitude"), raw.get("longitude"))
    factors = []
    for number, key in enumerate(FACTOR_FIELDS, start=1):
        if label := canonical_factor(raw.get(key)):
            factors.append({"collision_id": collision_id, "vehicle_number": number, "factor": label})
    crash = {
        "collision_id": collision_id,
        "crash_datetime": when,
        "hour": known_hour,
        "borough": _clean(raw.get("borough")),
        "zip_code": _clean(raw.get("zip_code")),
        "latitude": lat,
        "longitude": lon,
        "on_street": _clean(raw.get("on_street_name")),
        "cross_street": _clean(raw.get("cross_street_name")),
        "off_street": _clean(raw.get("off_street_name")),
        **{column: _count(raw.get(field)) for column, field in COUNT_FIELDS.items()},
        "vehicle_types": [v for key in VEHICLE_FIELDS if (v := _clean(raw.get(key)))],
    }
    return crash, factors


def rule_view(crash: dict, factors: list[dict]) -> dict:
    """The record the risk-flag rules see: the crash plus its factor labels as a list."""
    return {**crash, "contributing_factors": [f["factor"] for f in factors]}


def _upsert(db: Session, rows: list[dict]) -> None:
    dialect = postgresql if db.get_bind().dialect.name == "postgresql" else sqlite
    stmt = dialect.insert(NycCrash).values(rows)
    updates = {c.name: stmt.excluded[c.name] for c in NycCrash.__table__.columns if c.name != "collision_id"}
    db.execute(stmt.on_conflict_do_update(index_elements=["collision_id"], set_=updates))


def load_file(db: Session, path: Path, rules: list[Rule], *, scope: str = "full", batch_size: int = 2000, log=print) -> dict:
    """Insert or update every crash in a raw file. Safe to re-run: existing crashes are
    updated in place and their factors and flags are replaced."""
    started = utcnow()
    loaded = skipped = no_coordinates = 0
    for chunk in batched(iter_raw(path), batch_size):
        parsed: dict[str, tuple[dict, list[dict]]] = {}
        for raw in chunk:
            if result := parse_record(raw):
                parsed[result[0]["collision_id"]] = result  # last copy wins if the API repeats a row
            else:
                skipped += 1
        if not parsed:
            continue
        ids = list(parsed)
        db.execute(delete(NycCrashFactor).where(NycCrashFactor.collision_id.in_(ids)))
        db.execute(delete(CrashFlag).where(CrashFlag.source == "nyc", CrashFlag.crash_id.in_(ids)))
        _upsert(db, [crash for crash, _ in parsed.values()])
        bulk_insert(db, NycCrashFactor, [f for _, factors in parsed.values() for f in factors])
        bulk_insert(db, CrashFlag, [{"source": "nyc", "crash_id": cid, "flag_id": flag}
                                    for cid, (crash, factors) in parsed.items() for flag in flag_ids(rule_view(crash, factors), rules)])
        db.commit()
        loaded += len(parsed)
        no_coordinates += sum(1 for crash, _ in parsed.values() if crash["latitude"] is None)
        if loaded % 100_000 < batch_size:
            log(f"  nyc: {loaded:,} rows loaded")
    record_run(db, source="nyc", scope=scope, url=DATASET_URL, loaded=loaded, skipped=skipped, started=started)
    db.commit()
    return {"loaded": loaded, "skipped": skipped, "without_coordinates": no_coordinates}
