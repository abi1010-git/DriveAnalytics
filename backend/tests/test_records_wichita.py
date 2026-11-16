from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import wichita


def ms(*args):  # ACCIDENT_DATE holds local wall time as if it were UTC
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def row(incident="26C900001", offense="MOTOR VEHICLE/MOTOR VEHICLE IN TRANSPORT", **extra):
    raw = {"OBJECTID": 1, "INCIDENTID": incident, "ACCIDENT_DATE": ms(2026, 11, 14, 14, 49),
           "INTERSECTION": "E PAWNEE AVE & S HILLSIDE ST", "LOCATION": "2400 E PAWNEE AVE", "CROSS_STREET": "",
           "CITY": "WICHITA", "STATE": "KS", "POSTAL_CODE": 67211, "OFFENSE_CO": 7030, "OFFENSE_DE": offense,
           "LATITUDE": 37.6501, "LONGITUDE": -97.3079, "YEAR_": 2026, "MONTH_": 11, "DOW_": 7, "DOWFULL": "Saturday",
           "_lat": 37.6501, "_lon": -97.3079}
    raw.update(extra)
    return raw


def test_registered_all_layer_from_2021():
    spec = records.all_specs()["wichita"]
    assert spec is wichita.SPEC and spec.url.endswith("/FeatureServer/4") and spec.epoch_is_local
    assert "2021-01-01" in spec.where


def test_parse_local_time_no_counts():
    r = wichita.parse(row())
    assert r["source_id"] == "26C900001" and r["crash_datetime"] == datetime(2026, 11, 14, 14, 49)
    assert r["crash_datetime"].strftime("%A") == "Saturday"  # matches DOWFULL as stored
    assert r["injured"] is None and r["killed"] is None and r["severity"] is None
    assert r["crash_type"] == "MOTOR VEHICLE/MOTOR VEHICLE IN TRANSPORT" and r["road"] == "2400 E PAWNEE AVE"
    assert r["hit_and_run"] is None
    assert wichita.parse(row(offense="NON-INJURY CRASH/HIT AND RUN/UNDER $1000"))["hit_and_run"] is True
    assert wichita.parse(row(LATITUDE=0, LONGITUDE=0, _lat=None, _lon=None))["latitude"] is None


def test_offense_rows_merge(tmp_path):
    def get(url):
        if "returnCountOnly" in parse_qs(urlparse(url).query):
            return {"count": 4}
        return {"features": [{"attributes": row("22C1", LOCATION=None)},
                             {"attributes": row("22C1", "MOTOR VEHICLE/FIXED OBJECT")},
                             {"attributes": row("22C1", "NON-INJURY CRASH/HIT AND RUN/UNDER $1000")},
                             {"attributes": row("22C2")}]}
    path = base.fetch(wichita.SPEC, None, raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(wichita.SPEC, base.iter_raw(path))
    one = next(r for r in parsed if r["source_id"] == "22C1")
    assert len(parsed) == 2 and skipped == 0
    assert one["crash_type"] == ("MOTOR VEHICLE/MOTOR VEHICLE IN TRANSPORT; MOTOR VEHICLE/FIXED OBJECT; "
                                 "NON-INJURY CRASH/HIT AND RUN/UNDER $1000")
    assert one["hit_and_run"] is True and one["road"] == "2400 E PAWNEE AVE"
