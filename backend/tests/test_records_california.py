from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import california as ca


def row(cid=5300001, when="2026-09-05T03:32:00", **extra):
    raw = {"_id": 1, "Collision Id": cid, "Report Number": "9999-2026-00001", "Is Preliminary": "False",
           "Crash Date Time": when, "City Name": "Unincorporated", "NumberInjured": 2, "NumberKilled": 0,
           "Collision Type Description": "REAR END", "Weather 1": "CLEAR", "LightingDescription": "DAYLIGHT",
           "HitRun": None, "IsDeleted": "False", "Latitude": 34.07, "Longitude": -117.4, "PrimaryRoad": "I-10 W/B",
           "SecondaryRoad": "MAPLE AVE", "Primary Collision Factor Violation": "VC 22350 UNSAFE SPEED"}
    raw.update(extra)
    return raw


def test_registered_with_year_resources():
    spec = records.all_specs()["california"]
    assert spec is ca.SPEC and spec.platform == "ckan" and len(spec.urls) == 6
    assert spec.urls[0] == "b8ce0ca4-b4e9-490d-b4d1-1f4ec48cbefb" and spec.id_field == "Collision Id"


def test_parse_fields():
    r = ca.parse(row())
    assert r["source_id"] == "5300001" and r["crash_datetime"] == datetime(2026, 9, 5, 3, 32)
    assert (r["latitude"], r["longitude"]) == (34.07, -117.4)
    assert r["injured"] == 2 and r["killed"] == 0 and r["severity"] is None
    assert r["road"] == "I-10 W/B & MAPLE AVE" and r["primary_cause"] == "VC 22350 UNSAFE SPEED"
    assert r["crash_type"] == "REAR END" and r["weather"] == "CLEAR" and r["lighting"] == "DAYLIGHT"
    assert r["hit_and_run"] is None


def test_hit_run_deleted_and_missing_coordinates():
    assert ca.parse(row(HitRun="F"))["hit_and_run"] is True and ca.parse(row(HitRun="M"))["hit_and_run"] is True
    assert ca.parse(row(IsDeleted="True")) is None
    r = ca.parse(row(Latitude=None, Longitude=None, SecondaryRoad=None))
    assert r["latitude"] is None and r["road"] == "I-10 W/B"
    assert ca.parse(row(Latitude=40.7, Longitude=-74.0))["latitude"] is None  # outside California


def test_ckan_keyset_paging_over_resources(tmp_path):
    spec = base.SourceSpec(**{**ca.SPEC.__dict__, "urls": ca.SPEC.urls[:2], "page_size": 2})
    sqls = []
    def get(url):
        sqls.append(parse_qs(urlparse(url).query)["sql"][0])
        pages = {1: [row(1), row(2)], 2: [row(3)], 3: [row(3)]}  # id 3 also in the second year: kept once
        return {"success": True, "result": {"records": pages[len(sqls)]}}
    path = base.fetch(spec, datetime(2026, 9, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(spec, base.iter_raw(path))
    assert sorted(r["source_id"] for r in parsed) == ["1", "2", "3"] and skipped == 0
    assert f'FROM "{ca.SPEC.urls[0]}"' in sqls[0] and f'FROM "{ca.SPEC.urls[1]}"' in sqls[2]
    assert "\"IsDeleted\" IS DISTINCT FROM 'True'" in sqls[0] and "\"Crash Date Time\" >= '2026-09-01 00:00:00'" in sqls[0]
    assert '"Collision Id" > 2' in sqls[1] and 'ORDER BY "Collision Id" LIMIT 2' in sqls[0]
