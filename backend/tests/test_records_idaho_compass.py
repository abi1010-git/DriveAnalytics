from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import idaho_compass as ida


def row(serial="25C000001", text="2025-12-31 12:22:00", day=1767139200000, **extra):
    raw = {"objectid": 1, "serialnumber": serial, "accidentdate": text, "accidenttime": "12:22:00", "accident_date": day,
           "street1": "Caldwell Blvd", "street2": "Northside Blvd", "referencestreet": None, "severity": "B Injury Accident",
           "fatalities": 0, "injuries": 2, "numberofinjuries": 2, "light": "Day", "weather": "Clear", "year": 2025,
           "countyname": "Canyon", "agencycaseid": "X1", "latitude": 43.6, "longitude": -116.6, "_lat": 43.61, "_lon": -116.61}
    raw.update(extra)
    return raw


def test_registered():
    spec = records.all_specs()["idaho_compass"]
    assert spec is ida.SPEC and "Ada & Canyon counties, ID" in spec.label
    assert spec.order_field == "objectid" and spec.refresh_days == 30


def test_parse_fields():
    r = ida.parse(row())
    assert r["source_id"] == "25C000001" and r["crash_datetime"] == datetime(2025, 12, 31, 12, 22)
    assert r["injured"] == 2 and r["killed"] == 0 and r["severity"] == "B Injury Accident"
    assert r["road"] == "Caldwell Blvd & Northside Blvd" and (r["latitude"], r["longitude"]) == (43.61, -116.61)
    assert r["weather"] == "Clear" and r["lighting"] == "Day" and r["crash_type"] is None


def test_text_date_formats_and_fallbacks():
    assert ida.parse(row(text="11/7/2020 01:54"))["crash_datetime"] == datetime(2020, 11, 7, 1, 54)
    assert ida.parse(row(text="6/19/2023 3:49:00 PM"))["crash_datetime"] == datetime(2023, 6, 19, 15, 49)
    assert ida.parse(row(text="12/29/2019 -U"))["crash_datetime"] == datetime(2019, 12, 29)
    assert ida.parse(row(text=None))["crash_datetime"] == datetime(2025, 12, 31)  # accident_date is UTC midnight
    assert ida.parse(row(text=None, day=None))["crash_datetime"] is None
    assert ida.parse(row(street2=None))["road"] == "Caldwell Blvd"


def test_fetch_orders_by_lowercase_objectid(tmp_path):
    seen = []
    def get(url):
        query = parse_qs(urlparse(url).query)
        if "returnCountOnly" in query:
            return {"count": 2}
        seen.append(query)
        return {"features": [{"attributes": row("A")}, {"attributes": row("A")}]}
    path = base.fetch(ida.SPEC, datetime(2025, 12, 1), raw_dir=tmp_path, get=get, log=lambda *_: None)
    parsed, _ = base.parse_all(ida.SPEC, base.iter_raw(path))
    assert [r["source_id"] for r in parsed] == ["A"] and seen[0]["orderByFields"] == ["objectid"]
    assert "accident_date >= TIMESTAMP '2019-01-01 00:00:00'" in seen[0]["where"][0]
