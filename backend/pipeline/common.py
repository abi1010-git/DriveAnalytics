"""Helpers shared by the FARS and NYC loaders."""
import shutil
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models import IngestRun

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
USER_AGENT = "crash-data-loader/1.0"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def download(url: str, dest: Path, *, force: bool = False) -> Path:
    """Download url to dest unless it is already cached. Writes to a .part file first so a
    failed download never leaves a truncated file that looks complete."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    part.replace(dest)
    return dest


def batched(items: Iterable, size: int) -> Iterator[list]:
    iterator = iter(items)
    while chunk := list(islice(iterator, size)):
        yield chunk


def bulk_insert(db: Session, model, rows: list[dict]) -> None:
    if rows:
        db.execute(insert(model), rows)


def record_run(db: Session, *, source: str, scope: str, url: str, loaded: int, skipped: int, started: datetime) -> None:
    db.add(IngestRun(source=source, scope=scope, source_url=url, rows_loaded=loaded, rows_skipped=skipped,
                     started_at=started, finished_at=utcnow()))
