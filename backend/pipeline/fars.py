"""Load NHTSA FARS (Fatality Analysis Reporting System) national CSV files.

One zip per year from https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/.
We read two files from it:
  accident.csv - one row per fatal crash: where, when, conditions, road, fatalities
  vehicle.csv  - one row per vehicle: speeding (SPEEDREL), drinking driver (DR_DRINK), speed limit
Column names and codes were checked against the 2020 and 2024 files. Each code column
has a matching *NAME column with its label, which we store instead of keeping a lookup table.
"""
import csv
import io
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import CrashFlag, FarsCrash
from app.services.rule_engine import Rule, flag_ids

from .common import RAW_DIR, batched, bulk_insert, download, record_run, utcnow

URL = "https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/FARS{year}NationalCSV.zip"
# FARS fills unknown coordinates with repeated-digit codes instead of leaving them blank.
UNKNOWN_LATITUDES = {77.7777, 88.8888, 99.9999}
UNKNOWN_LONGITUDES = {777.7777, 888.8888, 999.9999}
SPEEDING_CODES = {2, 3, 4, 5}  # racing, exceeded limit, too fast for conditions, specifics unknown
_COUNTY_CODE_SUFFIX = re.compile(r"\s*\(\d+\)$")


def zip_path(year: int, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / "fars" / f"FARS{year}NationalCSV.zip"


def fetch(year: int, raw_dir: Path = RAW_DIR, force: bool = False) -> Path:
    return download(URL.format(year=year), zip_path(year, raw_dir), force=force)


def read_csv(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    """Read one CSV from the zip by file name, wherever it sits inside the archive.
    Most years are plain ASCII; some contain Windows-1252 characters such as the Ñ in
    "LA CAÑADA FLINTRIDGE", so we fall back to cp1252 when the bytes are not valid UTF-8."""
    member = next((m for m in archive.namelist() if Path(m).name.lower() == name.lower()), None)
    if member is None:
        raise ValueError(f"{name} not found in FARS archive")
    data = archive.read(member)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    return list(csv.DictReader(io.StringIO(text)))


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def vehicle_rollup(rows: list[dict[str, str]]) -> dict[int, dict]:
    """Collapse vehicle rows to one summary per crash (ST_CASE)."""
    out: dict[int, dict] = defaultdict(lambda: {"speeding_involved": False, "drinking_driver_involved": False, "max_speed_limit_mph": None})
    for row in rows:
        case = _int(row.get("ST_CASE"))
        if case is None:
            continue
        summary = out[case]
        if _int(row.get("SPEEDREL")) in SPEEDING_CODES:
            summary["speeding_involved"] = True
        if _int(row.get("DR_DRINK")) == 1:
            summary["drinking_driver_involved"] = True
        limit = _int(row.get("VSPD_LIM"))
        if limit is not None and 5 <= limit <= 95:  # 0 = no statutory limit, 98/99 = not reported/unknown
            current = summary["max_speed_limit_mph"]
            summary["max_speed_limit_mph"] = limit if current is None else max(current, limit)
    return out


def parse_accident(row: dict[str, str], year: int, vehicles: dict | None = None) -> dict:
    case = int(row["ST_CASE"])
    month, day = _int(row.get("MONTH")), _int(row.get("DAY"))
    try:
        crash_date = date(year, month, day) if month and day else None
    except ValueError:
        crash_date = None
    hour, minute = _int(row.get("HOUR")), _int(row.get("MINUTE"))
    lat, lon = _float(row.get("LATITUDE")), _float(row.get("LONGITUD"))
    if lat is None or lon is None or round(lat, 4) in UNKNOWN_LATITUDES or round(lon, 4) in UNKNOWN_LONGITUDES or lat == 0 or lon == 0:
        lat = lon = None
    county = _text(row.get("COUNTYNAME"))
    city = _text(row.get("CITYNAME"))
    record = {
        "id": f"{year}-{case}",
        "year": year,
        "st_case": case,
        "state_code": int(row["STATE"]),
        "state_name": _text(row.get("STATENAME")),
        "county_code": _int(row.get("COUNTY")),
        "county_name": _COUNTY_CODE_SUFFIX.sub("", county) if county else None,
        "city_name": None if _int(row.get("CITY")) in (0, None) or city in (None, "NOT APPLICABLE") else city,
        "crash_date": crash_date,
        "hour": hour if hour is not None and 0 <= hour <= 23 else None,
        "minute": minute if minute is not None and 0 <= minute <= 59 else None,
        "latitude": lat,
        "longitude": lon,
        "fatalities": _int(row.get("FATALS")) or 0,
        "persons": _int(row.get("PERSONS")),
        "pedestrians": _int(row.get("PEDS")),
        "vehicles": _int(row.get("VE_TOTAL")),
        "weather_code": _int(row.get("WEATHER")),
        "weather": _text(row.get("WEATHERNAME")),
        "light_code": _int(row.get("LGT_COND")),
        "light_condition": _text(row.get("LGT_CONDNAME")),
        "junction_code": _int(row.get("RELJCT2")),
        "junction": _text(row.get("RELJCT2NAME")),
        "intersection_type": _text(row.get("TYP_INTNAME")),
        "rural_urban": _text(row.get("RUR_URBNAME")),
        "road_class": _text(row.get("FUNC_SYSNAME")),
        "road_name": _text(row.get("TWAY_ID")),
        "cross_road_name": _text(row.get("TWAY_ID2")),
        "first_harmful_event": _text(row.get("HARM_EVNAME")),
        "collision_manner": _text(row.get("MAN_COLLNAME")),
        "speeding_involved": False,
        "drinking_driver_involved": False,
        "max_speed_limit_mph": None,
    }
    if vehicles and case in vehicles:
        record.update(vehicles[case])
    return record


def parse_year(path: Path, year: int) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        vehicles = vehicle_rollup(read_csv(archive, "vehicle.csv"))
        return [parse_accident(row, year, vehicles) for row in read_csv(archive, "accident.csv")]


def load_year(db: Session, path: Path, year: int, rules: list[Rule], batch_size: int = 5000) -> int:
    """Replace one year of FARS crashes (and their flags) in a single transaction, so a
    re-run gives the same result and a failed run leaves the previous load in place."""
    started = utcnow()
    records = parse_year(path, year)
    ids = [r["id"] for r in records]
    db.execute(delete(CrashFlag).where(CrashFlag.source == "fars", CrashFlag.crash_id.like(f"{year}-%")))
    db.execute(delete(FarsCrash).where(FarsCrash.year == year))
    for chunk in batched(records, batch_size):
        bulk_insert(db, FarsCrash, chunk)
        bulk_insert(db, CrashFlag, [{"source": "fars", "crash_id": r["id"], "flag_id": f} for r in chunk for f in flag_ids(r, rules)])
    record_run(db, source="fars", scope=str(year), url=URL.format(year=year), loaded=len(ids), skipped=0, started=started)
    db.commit()
    return len(ids)
