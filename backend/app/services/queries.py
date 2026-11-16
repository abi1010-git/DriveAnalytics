from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CrashFlag, FarsCrash, IngestRun, NycCrash
from .rule_engine import RuleSet


def _last_run(db: Session, source: str):
    return db.scalar(select(IngestRun).where(IngestRun.source == source).order_by(IngestRun.finished_at.desc()).limit(1))


def dataset_summary(db: Session) -> dict:
    fars_years = db.execute(select(FarsCrash.year, func.count(), func.sum(FarsCrash.fatalities)).group_by(FarsCrash.year).order_by(FarsCrash.year)).all()
    nyc_count, nyc_first, nyc_last, nyc_located = db.execute(
        select(func.count(), func.min(NycCrash.crash_datetime), func.max(NycCrash.crash_datetime), func.count(NycCrash.latitude))).one()
    fars_run, nyc_run = _last_run(db, "fars"), _last_run(db, "nyc")
    return {
        "fars": {
            "name": "NHTSA Fatality Analysis Reporting System",
            "coverage": "Every fatal motor vehicle crash on US public roads",
            "years": [{"year": y, "crashes": c, "fatalities": f or 0} for y, c, f in fars_years],
            "last_loaded": fars_run.finished_at if fars_run else None,
        },
        "nyc": {
            "name": "NYC Open Data - Motor Vehicle Collisions (Crashes)",
            "coverage": "Every police-reported crash in New York City",
            "crashes": nyc_count,
            "with_coordinates": nyc_located,
            "first_crash": nyc_first,
            "last_crash": nyc_last,
            "last_loaded": nyc_run.finished_at if nyc_run else None,
        },
    }


def flag_counts(db: Session, rules: RuleSet) -> list[dict]:
    counts = dict(((s, f), n) for s, f, n in db.execute(select(CrashFlag.source, CrashFlag.flag_id, func.count()).group_by(CrashFlag.source, CrashFlag.flag_id)).all())
    return [{**rule.model_dump(), "crashes_flagged": counts.get((rule.source, rule.id), 0)} for rule in rules.rules]


def flags_for(db: Session, source: str, crash_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {cid: [] for cid in crash_ids}
    if crash_ids:
        for cid, flag in db.execute(select(CrashFlag.crash_id, CrashFlag.flag_id).where(CrashFlag.source == source, CrashFlag.crash_id.in_(crash_ids))):
            out[cid].append(flag)
    return out
