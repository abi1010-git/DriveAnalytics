from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import st_louis_county as stl

MIDNIGHT_CST = 1794117600000  # 2026-11-08 06:00 UTC = 00:00 CST


def row(aid=2000001, **extra):
    raw = {"OBJECTID": 9, "Join_Count": 1, "TARGET_FID": 9, "Accident_ID": aid, "Report_Number": "26-000001",
           "Property_Damage_Only": 0, "Number_Injured": 2, "Number_Killed": 0, "Number_of_Vehicles": 2,
           "Accident_Date": MIDNIGHT_CST, "Accident_Time": 1730, "County": "ST. LOUIS", "Location_Speed_Limit": "35",
           "latdd": 38.6001, "londd": -90.4002, "On_Road": "MANCHESTER RD", "Cross_Road": "BALLAS RD",
           "district": "WEST COUNTY PRECINCT", "_lat": 38.6001, "_lon": -90.4002}
    raw.update(extra)
    return raw


def test_registered():
    assert records.all_specs()["st_louis_county"] is stl.SPEC and stl.SPEC.date_field == "Accident_Date"


def test_parse_date_plus_hhmm():
    r = stl.parse(row())
    assert r["source_id"] == "2000001" and r["crash_datetime"] == datetime(2026, 11, 8, 17, 30)
    assert r["injured"] == 2 and r["killed"] == 0 and r["severity"] is None and r["road"] == "MANCHESTER RD"
    assert stl.parse(row(Accident_Time=112))["crash_datetime"] == datetime(2026, 11, 8, 1, 12)
    assert stl.parse(row(Accident_Time=0))["crash_datetime"] == datetime(2026, 11, 8, 0, 0)
    assert stl.parse(row(Accident_Time=2460))["crash_datetime"] is None


def test_missing_ids_and_coordinates():
    assert stl.parse(row(aid=0, Report_Number=""))["source_id"] is None
    assert stl.parse(row(latdd=0, londd=0, _lat=None, _lon=None))["latitude"] is None
    assert stl.parse(row(latdd=None, londd=None))["latitude"] == 38.6001


def test_identical_join_rows_collapse(tmp_path):
    def get(url):
        if "returnCountOnly" in parse_qs(urlparse(url).query):
            return {"count": 4}
        return {"features": [{"attributes": row(5, OBJECTID=1)}, {"attributes": row(5, OBJECTID=2)},
                             {"attributes": row(6)}, {"attributes": row(0, Report_Number="")}]}
    path = base.fetch(stl.SPEC, None, raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(stl.SPEC, base.iter_raw(path))
    assert sorted(r["source_id"] for r in parsed) == ["5", "6"] and skipped == 1
