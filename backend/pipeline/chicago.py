"""Load City of Chicago "Traffic Crashes - Crashes" (Socrata dataset 85ca-t3if) into local_crashes.

Every crash on city streets reported to the Chicago Police Department (about 1.1M rows,
updated daily). Like the NYC loader we page through the public SODA API into a gzipped
JSON-lines file, then load that file, so loading rules can change without re-downloading.

Facts checked against the live API and dataset description (Nov 2026):
- Coverage: the description says E-Crash data exist "for some police districts in 2015, but
  citywide data are not available until September 2017". The table holds a handful of 2013-2014
  rows and partial 2015-2016 years; only Sept 2017 onwards is complete citywide. Crashes on
  interstates, freeway ramps and boundary roads where CPD is not the responding agency are excluded.
- crash_record_id is a 128-character lowercase hex string, unique per crash and the link to the
  Vehicles and People datasets. It sorts as plain text, so it is used for keyset paging.
- crash_date is a floating timestamp (no zone) in Chicago local time; it is stored as published.
- numbers arrive as strings and empty fields are left out of the JSON.
- hit_and_run_i is "Y", "N" or absent (absent on about two thirds of rows). Absent is stored as
  None rather than assumed to mean "N".
- some rows have 0/0 coordinates; those and anything outside the city box are dropped.
- text values ("UNABLE TO DETERMINE", "NOT APPLICABLE", "UNKNOWN", ...) are kept as published.
"""
import gzip
import json
import re
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import LocalCrash

from .common import USER_AGENT, RAW_DIR, batched, record_run, utcnow

SOURCE = "chicago"
DATASET_URL = "https://data.cityofchicago.org/resource/85ca-t3if.json"
ID_FIELD = "crash_record_id"
SELECT_FIELDS = [ID_FIELD, "crash_date", "latitude", "longitude", "street_no", "street_direction", "street_name",
                 "injuries_total", "injuries_fatal", "most_severe_injury", "prim_contributory_cause",
                 "weather_condition", "lighting_condition", "first_crash_type", "hit_and_run_i"]
# LocalCrash column -> Chicago field, for the plain text columns.
TEXT_FIELDS = {"severity": "most_severe_injury", "primary_cause": "prim_contributory_cause",
               "weather": "weather_condition", "lighting": "lighting_condition", "crash_type": "first_crash_type"}
# A generous box around the city limits (published points span roughly 41.64-42.02, -87.94 to -87.52).
CHICAGO_BOUNDS = {"lat": (41.60, 42.10), "lon": (-88.00, -87.50)}
_SPACES = re.compile(r"\s+")


def raw_path(raw_dir: Path = RAW_DIR, since: str | None = None) -> Path:
    name = f"crashes_updated_since_{since}.jsonl.gz" if since else "crashes_full.jsonl.gz"
    return raw_dir / SOURCE / name


def page_url(after_id: str | None, limit: int, since: str | None) -> str:
    """Keyset paging on crash_record_id (unique, fixed-length hex text, so text order is total and
    stable) instead of $offset, which slows down with depth and can skip or repeat rows when the
    data changes mid-download."""
    where = []
    if after_id:
        where.append(f"{ID_FIELD} > '{after_id}'")
    if since:
        where.append(f":updated_at >= '{since}T00:00:00'")
    params = {"$select": ",".join(SELECT_FIELDS), "$order": ID_FIELD, "$limit": str(limit)}
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
                log(f"  chicago: {total:,} rows downloaded")
            if len(rows) < page_size:
                break
            after_id = rows[-1][ID_FIELD]
    part.replace(dest)
    return dest


def _fetch_page(url: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def iter_raw(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _clean(value) -> str | None:
    value = _SPACES.sub(" ", str(value or "")).strip()
    return value or None


def _count(value) -> int | None:
    """None when the field is absent or unreadable; the table keeps "unknown" distinct from 0."""
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return None


def _coordinate(lat_raw, lon_raw) -> tuple[float | None, float | None]:
    try:
        lat, lon = float(lat_raw), float(lon_raw)
    except (TypeError, ValueError):
        return None, None
    (lat_min, lat_max), (lon_min, lon_max) = CHICAGO_BOUNDS["lat"], CHICAGO_BOUNDS["lon"]
    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
        return lat, lon
    return None, None


def _road(raw: dict) -> str | None:
    number = _clean(raw.get("street_no"))
    if number and re.fullmatch(r"\d+\.0+", number):
        number = number.split(".")[0]
    parts = [number, _clean(raw.get("street_direction")), _clean(raw.get("street_name"))]
    return " ".join(p for p in parts if p) or None


def _hit_and_run(value) -> bool | None:
    flag = _clean(value)
    if flag is None:
        return None
    return {"Y": True, "N": False}.get(flag.upper())


def parse_record(raw: dict) -> dict | None:
    """Turn one API row into a local_crashes row. Returns None for rows without an id or a
    readable crash date."""
    source_id = _clean(raw.get(ID_FIELD))
    crash_date = _clean(raw.get("crash_date"))
    if not source_id or not crash_date:
        return None
    try:
        when = datetime.fromisoformat(crash_date[:19])  # floating local time, e.g. 2026-11-15T01:20:00.000
    except ValueError:
        return None
    if when.tzinfo is not None:  # not expected; keep the published wall-clock time
        when = when.replace(tzinfo=None)
    lat, lon = _coordinate(raw.get("latitude"), raw.get("longitude"))
    return {
        "source": SOURCE,
        "source_id": source_id,
        "crash_datetime": when,
        "latitude": lat,
        "longitude": lon,
        "road": _road(raw),
        "injured": _count(raw.get("injuries_total")),
        "killed": _count(raw.get("injuries_fatal")),
        **{column: _clean(raw.get(field)) for column, field in TEXT_FIELDS.items()},
        "hit_and_run": _hit_and_run(raw.get("hit_and_run_i")),
    }


def _upsert(db: Session, rows: list[dict]) -> None:
    dialect = postgresql if db.get_bind().dialect.name == "postgresql" else sqlite
    stmt = dialect.insert(LocalCrash).values(rows)
    keys = ("source", "source_id")
    updates = {c.name: stmt.excluded[c.name] for c in LocalCrash.__table__.columns if c.name not in keys}
    db.execute(stmt.on_conflict_do_update(index_elements=list(keys), set_=updates))


def load_file(db: Session, path: Path, *, scope: str = "full", batch_size: int = 2000, log=print) -> dict:
    """Insert or update every crash in a raw file. Safe to re-run: existing rows are updated in place."""
    started = utcnow()
    loaded = skipped = no_coordinates = 0
    for chunk in batched(iter_raw(path), batch_size):
        parsed: dict[str, dict] = {}
        for raw in chunk:
            if row := parse_record(raw):
                parsed[row["source_id"]] = row  # last copy wins if the API repeats a row
            else:
                skipped += 1
        if not parsed:
            continue
        _upsert(db, list(parsed.values()))
        db.commit()
        loaded += len(parsed)
        no_coordinates += sum(1 for row in parsed.values() if row["latitude"] is None)
        if loaded % 100_000 < batch_size:
            log(f"  chicago: {loaded:,} rows loaded")
    record_run(db, source=SOURCE, scope=scope, url=DATASET_URL, loaded=loaded, skipped=skipped, started=started)
    db.commit()
    return {"loaded": loaded, "skipped": skipped, "without_coordinates": no_coordinates}
