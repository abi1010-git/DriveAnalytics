"""Keep every source current with one long-running process:

    python -m pipeline schedule              live feeds every 10 min, crash reports daily

Jobs run one at a time (so they never write the same rows concurrently), each in its own
session, and a failing job is logged and retried at its next turn instead of stopping the
loop. Daily jobs only fetch what changed: NYC and Chicago since their last successful run,
record portals from shortly before the newest crash they hold.
"""
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models import IngestRun

from .common import utcnow


@dataclass
class Job:
    name: str
    every: timedelta
    run: Callable[[], str]
    last_run: datetime | None = None

    def due(self, now: datetime) -> bool:
        return self.last_run is None or now - self.last_run >= self.every


def _last_success(db, source: str) -> datetime | None:
    return db.scalar(select(func.max(IngestRun.started_at)).where(IngestRun.source == source))


def build_jobs(session_factory, *, live_minutes: float = 10, daily_hours: float = 24) -> list[Job]:
    from . import chicago, nyc, records
    from .live import ADAPTERS
    from .live.poller import poll_source
    from .records.base import update

    def live() -> str:
        parts = []
        for adapter in ADAPTERS.values():
            with session_factory() as db:
                poll = poll_source(db, adapter)
                parts.append(f"{adapter.SOURCE} {'ERR' if poll.error else f'+{poll.inserted}/~{poll.updated}'}")
        return ", ".join(parts)

    def incremental(module, source: str) -> Callable[[], str]:
        def job() -> str:
            with session_factory() as db:
                last = _last_success(db, source)
                # Re-read a day before the last run; both portals filter on :updated_at, so this
                # also catches older crashes the police amended since then.
                since = (last - timedelta(days=1)).strftime("%Y-%m-%d") if last else None
                path = module.fetch(since=since, force=True, log=lambda *_: None)
                if source == "nyc":
                    from app.services.rule_engine import load_rules
                    result = module.load_file(db, path, load_rules().for_source("nyc"), scope=f"since {since}" if since else "full", log=lambda *_: None)
                else:
                    result = module.load_file(db, path, scope=f"since {since}" if since else "full", log=lambda *_: None)
            return f"{result['loaded']:,} rows since {since or 'the beginning'}"
        return job

    def record_portals() -> str:
        parts = []
        for name, spec in records.all_specs().items():
            try:
                with session_factory() as db:
                    parts.append(f"{name} {update(db, spec, log=lambda *_: None)['loaded']:,}")
            except Exception as exc:  # noqa: BLE001 - one portal must not stop the rest
                parts.append(f"{name} FAILED ({type(exc).__name__})")
        return ", ".join(parts)

    day = timedelta(hours=daily_hours)
    return [Job("live", timedelta(minutes=live_minutes), live),
            Job("nyc", day, incremental(nyc, "nyc")),
            Job("chicago", day, incremental(chicago, "chicago")),
            Job("records", day, record_portals)]


def run(jobs: list[Job], *, tick_seconds: float = 30, clock=utcnow, sleep=time.sleep, log=print, max_ticks: int | None = None) -> None:
    ticks = 0
    while max_ticks is None or ticks < max_ticks:
        for job in jobs:
            now = clock()
            if not job.due(now):
                continue
            job.last_run = now  # set first, so a failing job waits for its next turn
            started = time.perf_counter()
            try:
                summary = job.run()
                log(f"[{now:%Y-%m-%d %H:%M}Z] {job.name}: {summary} ({time.perf_counter() - started:.0f}s)")
            except Exception as exc:  # noqa: BLE001
                log(f"[{now:%Y-%m-%d %H:%M}Z] {job.name}: FAILED {type(exc).__name__}: {exc}")
                traceback.print_exc()
        ticks += 1
        if max_ticks is None or ticks < max_ticks:
            sleep(tick_seconds)
