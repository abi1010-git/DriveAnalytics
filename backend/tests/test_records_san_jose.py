from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import san_jose


def ms(*args):  # CRASHDATETIME holds local wall time as if it were UTC
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def row(tcr="26-300-0001", **extra):
    raw = {"OBJECTID": 1, "TCRNUMBER": tcr, "CRASHNAME": "CR-0000100001", "CRASHDATETIME": ms(2026, 11, 8, 17, 44),
           "CRASHDATETIMEUTC": ms(2026, 11, 9, 1, 44), "HOUR": 17, "YEAR": "2026", "VEHICLECOUNT": 2,
           "VEHICLEPARTYCATEGORY": "Driver, Driver", "MINORINJURIES": 2, "MODERATEINJURIES": 1, "SEVEREINJURIES": 1,
           "FATALINJURIES": 1, "KSIINJURIES": 2, "INJURYSEVERITY": "Fatal, Severe, Moderate, Minor",
           "PRIMARYCOLLISIONFACTOR": "Violation Driver 1", "WEATHER": "Clear", "LIGHTING": "Daylight",
           "COLLISIONTYPE": "Head On", "HITANDRUNFLAG": "False", "INTASTREETNAME": "TULLY RD", "INTBSTREETNAME": "KING RD",
           "NARRATIVE": "invented narrative", "AGERANGE": "30-49", "LATITUDE": 37.3301, "LONGITUDE": -121.8302,
           "_lat": 37.3301, "_lon": -121.8302}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["san_jose"]
    assert spec is san_jose.SPEC and spec.epoch_is_local and spec.reduce is san_jose.reduce


def test_parse_fields():
    r = san_jose.parse(row())
    assert r["source_id"] == "26-300-0001" and r["crash_datetime"] == datetime(2026, 11, 8, 17, 44)
    assert r["injured"] == 4 and r["killed"] == 1 and r["severity"] == "Fatal, Severe, Moderate, Minor"
    assert r["primary_cause"] == "Violation Driver 1" and r["crash_type"] == "Head On" and r["road"] == "TULLY RD"
    assert r["weather"] == "Clear" and r["lighting"] == "Daylight" and r["hit_and_run"] is False
    assert "invented narrative" not in str(r) and "30-49" not in str(r)  # people details are not stored
    assert san_jose.parse(row(HITANDRUNFLAG="True"))["hit_and_run"] is True


def test_pdo_and_old_rows():
    pdo = san_jose.parse(row(INJURYSEVERITY=None, MINORINJURIES=0, MODERATEINJURIES=0, SEVEREINJURIES=0, FATALINJURIES=0))
    assert pdo["injured"] == 0 and pdo["killed"] == 0 and pdo["severity"] is None
    blank = san_jose.parse(row(MINORINJURIES=None, MODERATEINJURIES=None, SEVEREINJURIES=None, FATALINJURIES=None))
    assert blank["injured"] is None and blank["killed"] is None
    assert san_jose.parse(row(CRASHDATETIME=ms(2005, 3, 1, 8, 0)))["crash_datetime"] is None


def test_repeated_crash_counts_taken_once(tmp_path):
    def get(url):
        if "returnCountOnly" in parse_qs(urlparse(url).query):
            return {"count": 3}
        return {"features": [{"attributes": row("A")}, {"attributes": row("A", OBJECTID=2, WEATHER=None)},
                             {"attributes": row("B")}]}
    path = base.fetch(san_jose.SPEC, None, raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, skipped = base.parse_all(san_jose.SPEC, base.iter_raw(path))
    a = next(r for r in parsed if r["source_id"] == "A")
    assert len(parsed) == 2 and skipped == 0
    assert a["injured"] == 4 and a["killed"] == 1 and a["weather"] == "Clear"  # not 8 / 2
