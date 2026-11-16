"""Command-line entry point for the crash data pipeline.

    python -m pipeline fars --years 2020-2024     download (if not cached) and load FARS years
    python -m pipeline nyc                        download all NYC crashes and load them
    python -m pipeline nyc --since 2026-11-01     only rows created or updated on/after a date
    python -m pipeline nyc --file path.jsonl.gz   load an already-downloaded file
    python -m pipeline live                       poll every live incident feed once
    python -m pipeline live --every 10            keep polling every 10 minutes

Set DATABASE_URL to load into PostgreSQL; the default is a local SQLite file.
"""
import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.rule_engine import load_rules  # noqa: E402

from . import fars, nyc  # noqa: E402
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
    live_cmd = commands.add_parser("live", help="poll live traffic-incident feeds")
    live_cmd.add_argument("--source", action="append", help="only these sources (default: all)")
    live_cmd.add_argument("--every", type=float, metavar="MINUTES", help="keep polling on this interval")
    live_cmd.add_argument("--backfill-days", type=float, default=7, help="history to fetch the first time a source is polled")
    args = parser.parse_args(argv)

    Base.metadata.create_all(engine)
    if args.command == "live":
        from .live import ADAPTERS
        from .live.poller import run
        unknown = set(args.source or []) - set(ADAPTERS)
        if unknown:
            parser.error(f"unknown source(s): {', '.join(sorted(unknown))}; choose from {', '.join(ADAPTERS)}")
        adapters = [ADAPTERS[name] for name in (args.source or ADAPTERS)]
        run(SessionLocal, adapters, every_minutes=args.every, backfill=timedelta(days=args.backfill_days))
        return
    rules = load_rules()
    started = time.perf_counter()
    with SessionLocal() as db:
        if args.command == "fars":
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
