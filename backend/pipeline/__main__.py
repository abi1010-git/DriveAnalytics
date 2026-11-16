"""Command-line entry point for the crash data pipeline.

    python -m pipeline fars --years 2020-2024     download (if not cached) and load FARS years
    python -m pipeline nyc                        download all NYC crashes and load them
    python -m pipeline nyc --since 2026-11-01     only rows created or updated on/after a date
    python -m pipeline nyc --file path.jsonl.gz   load an already-downloaded file
    python -m pipeline chicago [--since DATE]     download and load Chicago crash records
    python -m pipeline records                    update every crash-record portal (first run loads full history)
    python -m pipeline records --source NAME      just one; --full re-reads everything
    python -m pipeline live                       poll every live incident feed once
    python -m pipeline live --every 10            keep polling every 10 minutes
    python -m pipeline schedule                   keep everything current: live every 10 min, the rest daily
    python -m pipeline export --out DIR           write the static site's JSON files (docs/STATIC_SITE.md)

Set DATABASE_URL to load into PostgreSQL; the default is a local SQLite file.
"""
import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.rule_engine import load_rules  # noqa: E402

from . import chicago, fars, nyc  # noqa: E402
from .common import RAW_DIR  # noqa: E402


def year_range(text: str) -> list[int]:
    if "-" in text:
        start, end = (int(part) for part in text.split("-", 1))
        return list(range(start, end + 1))
    return [int(part) for part in text.split(",")]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="where downloaded files are cached")
    commands = parser.add_subparsers(dest="command", required=True)
    fars_cmd = commands.add_parser("fars", help="load NHTSA FARS fatal crashes")
    fars_cmd.add_argument("--years", default="2020-2024", help="e.g. 2024, 2020-2024 or 2019,2021")
    fars_cmd.add_argument("--redownload", action="store_true")
    nyc_cmd = commands.add_parser("nyc", help="load NYC Open Data motor vehicle collisions")
    nyc_cmd.add_argument("--since", type=date.fromisoformat, help="only rows updated on/after this date (YYYY-MM-DD)")
    nyc_cmd.add_argument("--file", type=Path, help="load this raw .jsonl.gz instead of downloading")
    nyc_cmd.add_argument("--redownload", action="store_true")
    chicago_cmd = commands.add_parser("chicago", help="load City of Chicago traffic crash records")
    chicago_cmd.add_argument("--since", type=date.fromisoformat, help="only rows updated on/after this date (YYYY-MM-DD)")
    chicago_cmd.add_argument("--file", type=Path, help="load this raw .jsonl.gz instead of downloading")
    chicago_cmd.add_argument("--redownload", action="store_true")
    records_cmd = commands.add_parser("records", help="load crash-record portals configured in pipeline/records/sources")
    records_cmd.add_argument("--source", action="append", help="only these sources (default: all)")
    records_cmd.add_argument("--full", action="store_true", help="re-read full history instead of only recent rows")
    schedule_cmd = commands.add_parser("schedule", help="run forever: live feeds every 10 min, crash reports daily")
    schedule_cmd.add_argument("--live-minutes", type=float, default=10)
    schedule_cmd.add_argument("--daily-hours", type=float, default=24)
    schedule_cmd.add_argument("--jobs", default="live,nyc,chicago,records", help="comma-separated subset to run")
    export_cmd = commands.add_parser("export", help="write JSON files for the static site")
    export_cmd.add_argument("--out", type=Path, required=True)
    live_cmd = commands.add_parser("live", help="poll live traffic-incident feeds")
    live_cmd.add_argument("--source", action="append", help="only these sources (default: all)")
    live_cmd.add_argument("--every", type=float, metavar="MINUTES", help="keep polling on this interval")
    live_cmd.add_argument("--backfill-days", type=float, default=7, help="history to fetch the first time a source is polled")
    live_cmd.add_argument("--since", type=date.fromisoformat, help="re-read incremental feeds from this date (one-off history backfill)")
    args = parser.parse_args(argv)

    Base.metadata.create_all(engine)
    if args.command == "schedule":
        from .scheduler import build_jobs, run as run_schedule
        wanted = {name.strip() for name in args.jobs.split(",")}
        jobs = [job for job in build_jobs(SessionLocal, live_minutes=args.live_minutes, daily_hours=args.daily_hours) if job.name in wanted]
        if not jobs:
            parser.error("no jobs selected; choose from live, nyc, chicago, records")
        run_schedule(jobs)
        return
    if args.command == "export":
        from .export import run as export_run
        started = time.perf_counter()
        with SessionLocal() as db:
            meta = export_run(db, args.out)
        sizes = sum(f.stat().st_size for f in args.out.rglob("*.json"))
        print(f"export: {meta['fars_crashes']:,} FARS crashes, {meta['grid_cells']:,} grid cells, {meta['dots']:,} dots in "
              f"{len(meta['tiles'])} tiles, {meta['live_points']:,} live points; {sizes / 1e6:.1f} MB in {args.out} "
              f"({time.perf_counter() - started:.0f}s)")
        return
    if args.command == "records":
        from . import records
        from .records.base import update
        specs = records.all_specs()
        unknown = set(args.source or []) - set(specs)
        if unknown:
            parser.error(f"unknown source(s): {', '.join(sorted(unknown))}; choose from {', '.join(specs)}")
        for name in args.source or specs:
            started = time.perf_counter()
            try:
                with SessionLocal() as db:
                    result = update(db, specs[name], full=args.full)
                print(f"records {name}: {result['loaded']:,} loaded, {result['skipped']:,} skipped, "
                      f"{result['without_coordinates']:,} without coordinates ({time.perf_counter() - started:.0f}s)")
            except Exception as exc:  # noqa: BLE001 - one broken portal must not stop the rest
                print(f"records {name}: FAILED {type(exc).__name__}: {exc}")
        return
    if args.command == "live":
        from .live import ADAPTERS
        from .live.poller import run
        unknown = set(args.source or []) - set(ADAPTERS)
        if unknown:
            parser.error(f"unknown source(s): {', '.join(sorted(unknown))}; choose from {', '.join(ADAPTERS)}")
        adapters = [ADAPTERS[name] for name in (args.source or ADAPTERS)]
        since = datetime(args.since.year, args.since.month, args.since.day) if args.since else None
        run(SessionLocal, adapters, every_minutes=args.every, backfill=timedelta(days=args.backfill_days), since=since)
        return
    rules = load_rules()
    started = time.perf_counter()
    with SessionLocal() as db:
        if args.command == "chicago":
            since = args.since.isoformat() if args.since else None
            path = args.file or chicago.fetch(args.raw_dir, since=since, force=args.redownload)
            result = chicago.load_file(db, path, scope=f"since {since}" if since else "full")
            print(f"chicago: {result['loaded']:,} crashes loaded, {result['skipped']:,} skipped, "
                  f"{result['without_coordinates']:,} without usable coordinates")
        elif args.command == "fars":
            for year in year_range(args.years):
                path = fars.fetch(year, args.raw_dir, force=args.redownload)
                count = fars.load_year(db, path, year, rules.for_source("fars"))
                print(f"fars {year}: {count:,} crashes loaded from {path.name}")
        else:
            since = args.since.isoformat() if args.since else None
            path = args.file or nyc.fetch(args.raw_dir, since=since, force=args.redownload)
            result = nyc.load_file(db, path, rules.for_source("nyc"), scope=f"since {since}" if since else "full")
            print(f"nyc: {result['loaded']:,} crashes loaded, {result['skipped']:,} skipped, "
                  f"{result['without_coordinates']:,} without usable coordinates")
    print(f"done in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
