import csv
import gzip
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # tests never touch a real database

from app.database import Base  # noqa: E402
from app.services.rule_engine import load_rules  # noqa: E402

ACCIDENT_COLUMNS = ["STATE", "STATENAME", "ST_CASE", "PEDS", "VE_TOTAL", "PERSONS", "COUNTY", "COUNTYNAME", "CITY", "CITYNAME",
                    "MONTH", "DAY", "YEAR", "HOUR", "MINUTE", "TWAY_ID", "TWAY_ID2", "RUR_URB", "RUR_URBNAME", "FUNC_SYS", "FUNC_SYSNAME",
                    "LATITUDE", "LONGITUD", "HARM_EV", "HARM_EVNAME", "MAN_COLL", "MAN_COLLNAME", "RELJCT2", "RELJCT2NAME",
                    "TYP_INT", "TYP_INTNAME", "LGT_COND", "LGT_CONDNAME", "WEATHER", "WEATHERNAME", "FATALS"]
VEHICLE_COLUMNS = ["STATE", "ST_CASE", "VEH_NO", "SPEEDREL", "SPEEDRELNAME", "DR_DRINK", "DR_DRINKNAME", "VSPD_LIM"]


def accident(**overrides):
    row = {"STATE": "1", "STATENAME": "Alabama", "ST_CASE": "10001", "PEDS": "0", "VE_TOTAL": "1", "PERSONS": "1",
           "COUNTY": "125", "COUNTYNAME": "TUSCALOOSA (125)", "CITY": "0", "CITYNAME": "NOT APPLICABLE",
           "MONTH": "1", "DAY": "1", "YEAR": "2024", "HOUR": "10", "MINUTE": "30", "TWAY_ID": "SR-69", "TWAY_ID2": "",
           "RUR_URB": "1", "RUR_URBNAME": "Rural", "FUNC_SYS": "4", "FUNC_SYSNAME": "Minor Arterial",
           "LATITUDE": "33.47131111", "LONGITUD": "-87.496702780", "HARM_EV": "42", "HARM_EVNAME": "Tree (Standing Only)",
           "MAN_COLL": "0", "MAN_COLLNAME": "Not a collision", "RELJCT2": "1", "RELJCT2NAME": "Non-Junction",
           "TYP_INT": "1", "TYP_INTNAME": "Not an Intersection", "LGT_COND": "1", "LGT_CONDNAME": "Daylight",
           "WEATHER": "1", "WEATHERNAME": "Clear", "FATALS": "1"}
    row.update(overrides)
    return row


def vehicle(case, **overrides):
    row = {"STATE": "1", "ST_CASE": str(case), "VEH_NO": "1", "SPEEDREL": "0", "SPEEDRELNAME": "No", "DR_DRINK": "0",
           "DR_DRINKNAME": "No", "VSPD_LIM": "45"}
    row.update(overrides)
    return row


def _csv(columns, rows) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


@pytest.fixture
def fars_zip(tmp_path):
    """A tiny FARS archive in the real layout: a year folder holding accident.csv and vehicle.csv,
    with one cp1252 character as found in the real 2020 file."""
    def build(accidents, vehicles, year=2024, encoding="utf-8"):
        path = tmp_path / f"FARS{year}NationalCSV.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"FARS{year}NationalCSV/accident.csv", _csv(ACCIDENT_COLUMNS, accidents).encode(encoding))
            archive.writestr(f"FARS{year}NationalCSV/vehicle.csv", _csv(VEHICLE_COLUMNS, vehicles).encode(encoding))
        return path
    return build


def nyc_row(collision_id="abc1", **overrides):
    row = {"collision_id": collision_id, "crash_date": "2026-11-12T00:00:00.000", "crash_time": "16:40", "borough": "BROOKLYN",
           "zip_code": "11215", "latitude": "40.67", "longitude": "-73.98", "on_street_name": "4 AVE",
           "cross_street_name": "PRESIDENT ST", "number_of_persons_injured": "1", "number_of_persons_killed": "0",
           "number_of_pedestrians_injured": "1", "number_of_pedestrians_killed": "0", "number_of_cyclist_injured": "0",
           "number_of_cyclist_killed": "0", "number_of_motorist_injured": "0", "number_of_motorist_killed": "0",
           "contributing_factor_vehicle_1": "Failure to Yield Right-of-Way", "contributing_factor_vehicle_2": "Does Not Apply",
           "vehicle_type_code1": "Sedan", "vehicle_type_code2": "Bike"}
    row.update(overrides)
    return {k: v for k, v in row.items() if v is not None}


@pytest.fixture
def nyc_file(tmp_path):
    def build(rows, name="crashes.jsonl.gz"):
        path = tmp_path / name
        with gzip.open(path, "wt", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row) + "\n")
        return path
    return build


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="session")
def rules():
    return load_rules()
