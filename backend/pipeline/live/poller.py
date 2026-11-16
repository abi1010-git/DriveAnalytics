"""Poll live feeds and upsert their incidents into live_incidents."""
import json
import time
import traceback
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import LiveIncident, LivePoll

from ..common import USER_AGENT, batched, utcnow
from .base import CATEGORIES, FIELDS


def get_json(url: str, timeout: int = 60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _since(db: Session, source: str, backfill: timedelta, now: datetime) -> datetime:
    """Resume from the newest change we hold for this source; on the first run, go back `backfill`."""
    newest = db.scalar(select(func.max(func.coalesce(LiveIncident.updated_at, LiveIncident.reported_at))).where(LiveIncident.source == source))
    return newest or now - backfill


def poll_source(db: Session, adapter, *, now: datetime | None = None, backfill: timedelta = timedelta(days=7), get=get_json) -> LivePoll:
    """Fetch one source once and upsert. Errors are recorded on the poll row, not raised, so
    one broken feed never stops the others."""
    now = now or utcnow()
    poll = LivePoll(source=adapter.SOURCE, polled_at=now, fetched=0, inserted=0, updated=0, cleared=0)
    try:
        raws = adapter.fetch(None if adapter.SNAPSHOT else _since(db, adapter.SOURCE, backfill, now), get)
        parsed = {}
        for raw in raws:
            record = adapter.parse(raw)
            if record and record["category"] in CATEGORIES:
                parsed[record["source_id"]] = record  # last copy wins
        poll.fetched = len(parsed)
        for chunk in batched(list(parsed.values()), 1000):
            ids = [r["source_id"] for r in chunk]
            existing = {row.source_id: row for row in db.scalars(select(LiveIncident).where(
                LiveIncident.source == adapter.SOURCE, LiveIncident.source_id.in_(ids)))}
            for record in chunk:
                values = {key: record.get(key) for key in FIELDS}
                if values["status"] == "cleared":
                    values["cleared_at"] = record.get("updated_at") or now
                row = existing.get(record["source_id"])
                if row is None:
                    db.add(LiveIncident(source=adapter.SOURCE, first_seen_at=now, last_seen_at=now, **values))
                    poll.inserted += 1
                else:
                    if row.status == "cleared" and values["status"] == "cleared":
                        values["cleared_at"] = row.cleared_at or values.get("cleared_at")
                    changed = any(getattr(row, key) != value for key, value in values.items())
                    for key, value in values.items():
                        setattr(row, key, value)
                    row.last_seen_at = now
                    poll.updated += int(changed)
        if adapter.SNAPSHOT:
            # A snapshot lists every active incident, so active rows it no longer lists have cleared.
            result = db.execute(update(LiveIncident)
                                .where(LiveIncident.source == adapter.SOURCE, LiveIncident.status == "active",
                                       LiveIncident.source_id.not_in(list(parsed) or [""]))
                                .values(status="cleared", cleared_at=now))
            poll.cleared = result.rowcount or 0
        db.add(poll)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - record any feed failure and move on
        db.rollback()
        poll = LivePoll(source=adapter.SOURCE, polled_at=now, fetched=0, inserted=0, updated=0, cleared=0, error=f"{type(exc).__name__}: {exc}"[:2000])
        db.add(poll)
        db.commit()
        traceback.print_exc()
    return poll


def run(session_factory, adapters, *, every_minutes: float | None, backfill: timedelta, log=print) -> None:
    while True:
        started = time.monotonic()
        for adapter in adapters:
            with session_factory() as db:
                poll = poll_source(db, adapter, backfill=backfill)
                outcome = f"error: {poll.error}" if poll.error else f"{poll.fetched} fetched, {poll.inserted} new, {poll.updated} updated, {poll.cleared} cleared"
                log(f"[{poll.polled_at:%Y-%m-%d %H:%M:%S}Z] live {adapter.SOURCE}: {outcome}")
        if every_minutes is None:
            return
        time.sleep(max(0.0, every_minutes * 60 - (time.monotonic() - started)))
