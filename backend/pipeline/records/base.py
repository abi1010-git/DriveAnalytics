"""Configurable loader for crash-record portals (Socrata and ArcGIS) into local_crashes.

Each source is one small module in pipeline/records/sources/ that defines `SPEC`, a
SourceSpec saying where the data lives and how one raw row becomes a LocalCrash row.
The loader here does the rest: paging, the raw cache, incremental updates, de-duplication
and the upsert. See pipeline/records/sources/montgomery_md.py for a complete example.

Writing a new source (checklist):
  1. Query the real endpoint first; confirm the date field, id field, coordinates and
     whether rows are per crash or per person/vehicle (then set `dedupe` / `reduce`).
  2. Decide the time convention: Socrata "floating" timestamps are local wall time; ArcGIS
     date fields are epoch milliseconds, usually UTC, but some publishers store local time
     as if it were UTC (set epoch_is_local=True only after checking a known crash).
  3. Write parse(raw) -> dict with LocalCrash columns (see app/models/entities.py), using the
     helpers below; return None to skip a row. Never guess values a source doesn't publish.
  4. Add tests/test_records_<name>.py with fixture rows in the real field names.
"""
import gzip
import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import LocalCrash

from ..common import RAW_DIR, USER_AGENT, batched, record_run, utcnow

COLUMNS = ("crash_datetime", "latitude", "longitude", "road", "injured", "killed", "severity", "primary_cause",
           "weather", "lighting", "crash_type", "hit_and_run")


@dataclass
class SourceSpec:
    source: str                      # short id stored in local_crashes.source, e.g. "montgomery_md"
    label: str                       # shown in the app, e.g. "Montgomery County, MD crash reports"
    platform: str                    # "socrata", "arcgis" or "ckan"
    url: str                         # Socrata: https://host/resource/xxxx-xxxx.json; ArcGIS: .../FeatureServer/0 (or a list via `urls`);
                                     # CKAN: https://host/api/3/action/datastore_search_sql, with resource ids in `urls`
    date_field: str                  # field used for incremental updates and ordering
    parse: Callable[[dict], dict | None]
    states: list[int]                # FIPS state codes covered
    bbox: tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat), also used to drop bad coordinates
    tz: str = "America/New_York"     # local zone of the publisher (for building date filters)
    urls: list[str] = field(default_factory=list)  # sources split by year: ArcGIS layers/services, or CKAN resource ids
    id_field: str | None = None      # CKAN only: unique column used for stable paging (e.g. "Collision Id")
    order_field: str = "OBJECTID"    # ArcGIS only: the layer's object-id field, used to order pages
    where: str | None = None         # extra server-side filter, e.g. "crash_date >= '2015-01-01'"
    page_size: int = 2000            # ArcGIS servers often cap at 1000-2000; Socrata allows 50000
    overlap: timedelta = timedelta(days=3)  # re-read this much before the newest held record
    epoch_is_local: bool = False     # ArcGIS only: epoch values hold local wall time, not UTC
    reduce: Callable[[list[dict]], dict] | None = None  # combine several parsed rows of one crash (per-person data)
    notes: str = ""                  # coverage caveats shown in docs


# ---------- helpers for parse() ----------

_SPACES = re.compile(r"\s+")


def text(value) -> str | None:
    value = _SPACES.sub(" ", str(value)).strip() if value is not None else ""
    return value or None


def number(value) -> int | None:
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return None


def point(spec: SourceSpec, lat, lon) -> tuple[float | None, float | None]:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    min_lon, min_lat, max_lon, max_lat = spec.bbox
    return (lat, lon) if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon else (None, None)


def floating(value) -> datetime | None:
    """Socrata floating timestamp ("2026-11-12T16:40:00.000") -> naive local datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return None


def epoch(spec: SourceSpec, value) -> datetime | None:
    """ArcGIS epoch milliseconds -> naive local datetime in the source's zone."""
    try:
        moment = datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    if spec.epoch_is_local:
        return moment.replace(tzinfo=None)
    return moment.astimezone(ZoneInfo(spec.tz)).replace(tzinfo=None)


def sane(when: datetime | None, earliest: int = 2000) -> datetime | None:
    """Drop impossible dates (some portals hold years like 1825 or 2926)."""
    if when is None or when.year < earliest or when > datetime.now() + timedelta(days=2):
        return None
    return when


# ---------- fetching ----------

def get_json(url: str, timeout: int = 120):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _socrata_pages(spec: SourceSpec, since: datetime | None, get) -> Iterator[list[dict]]:
    """Order by the field and :id together so offset paging is stable."""
    where = [w for w in (spec.where, f"{spec.date_field} >= '{since:%Y-%m-%dT%H:%M:%S}'" if since else None) if w]
    offset = 0
    while True:
        params = {"$order": f"{spec.date_field}, :id", "$limit": str(spec.page_size), "$offset": str(offset)}
        if where:
            params["$where"] = " AND ".join(f"({w})" for w in where)
        page = get(f"{spec.url}?{urllib.parse.urlencode(params)}")
        if not isinstance(page, list):
            raise ValueError(f"unexpected Socrata response: {str(page)[:200]}")
        yield page
        if len(page) < spec.page_size:
            return
        offset += spec.page_size


def _arcgis_pages(spec: SourceSpec, since: datetime | None, get) -> Iterator[list[dict]]:
    """Page with resultOffset ordered by the object-id field; geometry is requested in WGS84 and merged
    into the attributes as _lon/_lat so parse() sees one flat dict."""
    for layer in spec.urls or [spec.url]:
        where = [w for w in (spec.where, f"{spec.date_field} >= TIMESTAMP '{since:%Y-%m-%d %H:%M:%S}'" if since else None) if w]
        offset = 0
        while True:
            params = {"where": " AND ".join(f"({w})" for w in where) or "1=1", "outFields": "*", "outSR": "4326",
                      "returnGeometry": "true", "orderByFields": spec.order_field, "resultOffset": str(offset),
                      "resultRecordCount": str(spec.page_size), "f": "json"}
            body = get(f"{layer.rstrip('/')}/query?{urllib.parse.urlencode(params)}")
            if "error" in body:
                raise ValueError(f"ArcGIS error from {layer}: {body['error']}")
            rows = []
            for feature in body.get("features", []):
                attrs = dict(feature.get("attributes") or {})
                geometry = feature.get("geometry") or {}
                attrs["_lon"], attrs["_lat"] = geometry.get("x"), geometry.get("y")
                rows.append(attrs)
            yield rows
            if not rows or not (body.get("exceededTransferLimit") or len(rows) >= spec.page_size):
                break
            offset += len(rows)


def _ckan_pages(spec: SourceSpec, since: datetime | None, get) -> Iterator[list[dict]]:
    """CKAN datastore via SQL: one resource per year in `urls`; keyset paging on id_field.
    Column names are quoted because CKAN tables often contain spaces ("Crash Date Time")."""
    if not spec.id_field:
        raise ValueError(f"{spec.source}: CKAN sources need id_field")
    q = lambda name: '"' + name.replace('"', '""') + '"'  # noqa: E731
    for resource in spec.urls:
        after = None
        while True:
            where = [w for w in (spec.where,
                                 f"{q(spec.date_field)} >= '{since:%Y-%m-%d %H:%M:%S}'" if since else None,
                                 f"{q(spec.id_field)} > {after!r}" if after is not None else None) if w]
            sql = (f"SELECT * FROM {q(resource)}" + (f" WHERE {' AND '.join(f'({w})' for w in where)}" if where else "")
                   + f" ORDER BY {q(spec.id_field)} LIMIT {int(spec.page_size)}")
            body = get(f"{spec.url}?{urllib.parse.urlencode({'sql': sql})}")
            if not body.get("success"):
                raise ValueError(f"CKAN error from {spec.url}: {str(body.get('error'))[:200]}")
            rows = body["result"]["records"]
            yield rows
            if len(rows) < spec.page_size:
                break
            after = rows[-1][spec.id_field]


def raw_path(spec: SourceSpec, since: datetime | None, raw_dir: Path = RAW_DIR) -> Path:
    name = f"updated_since_{since:%Y-%m-%d}.jsonl.gz" if since else "full.jsonl.gz"
    return raw_dir / "records" / spec.source / name


def fetch(spec: SourceSpec, since: datetime | None = None, *, raw_dir: Path = RAW_DIR, get=get_json, log=print) -> Path:
    """Download rows (all, or with date_field >= since) into a gzipped JSON-lines cache."""
    dest = raw_path(spec, since, raw_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    pages = {"socrata": _socrata_pages, "arcgis": _arcgis_pages, "ckan": _ckan_pages}[spec.platform]
    total = 0
    with gzip.open(part, "wt", encoding="utf-8") as out:
        for page in pages(spec, since, get):
            for row in page:
                out.write(json.dumps(row, default=str) + "\n")
            total += len(page)
            if total and total % 50000 < len(page):
                log(f"  {spec.source}: {total:,} rows downloaded")
    part.replace(dest)
    return dest


def iter_raw(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


# ---------- loading ----------

def _upsert(db: Session, rows: list[dict]) -> None:
    dialect = postgresql if db.get_bind().dialect.name == "postgresql" else sqlite
    stmt = dialect.insert(LocalCrash).values(rows)
    db.execute(stmt.on_conflict_do_update(index_elements=["source", "source_id"],
                                          set_={c: stmt.excluded[c] for c in COLUMNS}))


def parse_all(spec: SourceSpec, raws: Iterable[dict]) -> tuple[list[dict], int]:
    """Parse rows and collapse duplicates of one crash (per-person/vehicle datasets)."""
    groups: dict[str, list[dict]] = {}
    skipped = 0
    for raw in raws:
        record = spec.parse(raw)
        if not record or not record.get("source_id") or record.get("crash_datetime") is None:
            skipped += 1
            continue
        groups.setdefault(str(record["source_id"]), []).append(record)
    records = [(spec.reduce(rows) if spec.reduce and len(rows) > 1 else rows[-1]) for rows in groups.values()]
    return records, skipped


def load(db: Session, spec: SourceSpec, path: Path, *, scope: str, batch_size: int = 2000) -> dict:
    """Upsert a raw file into local_crashes. Safe to re-run. Per-person datasets are grouped
    per crash across the whole file, so it is parsed in one pass (fine at these sizes)."""
    started = utcnow()
    records, skipped = parse_all(spec, iter_raw(path))
    for chunk in batched(records, batch_size):
        _upsert(db, [{"source": spec.source, **{k: r.get(k) for k in ("source_id", *COLUMNS)}} for r in chunk])
        db.commit()
    record_run(db, source=spec.source, scope=scope[:60], url=spec.url, loaded=len(records), skipped=skipped, started=started)
    db.commit()
    return {"loaded": len(records), "skipped": skipped, "without_coordinates": sum(1 for r in records if r.get("latitude") is None)}


def newest_held(db: Session, spec: SourceSpec) -> datetime | None:
    from sqlalchemy import func, select
    return db.scalar(select(func.max(LocalCrash.crash_datetime)).where(LocalCrash.source == spec.source))


def update(db: Session, spec: SourceSpec, *, full: bool = False, raw_dir: Path = RAW_DIR, get=get_json, log=print) -> dict:
    """Full load the first time (or with full=True); afterwards only rows from `overlap`
    before the newest crash held, so daily runs stay small."""
    newest = None if full else newest_held(db, spec)
    since = newest - spec.overlap if newest else None
    path = fetch(spec, since, raw_dir=raw_dir, get=get, log=log)
    return load(db, spec, path, scope=f"since {since:%Y-%m-%d}" if since else "full")
