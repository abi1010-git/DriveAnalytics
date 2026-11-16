from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import colorado_springs as cs


def cs_row(rid="2026-00400001", **extra):
    row = {"accidentnumber": rid, "accidentdatetime": "2026-11-09T16:45:00.000", "vehicletype": "Automobile",
           "driveraction": "FOLLOWED TO CLOSELY", "firstharmfulevent": "Front to Rear", "involved_injury_": "Yes",
           "numberofinjured": "2", "involved_death_": "No", "numberofkilled": "0",
           "streetaddress": "N ACADEMY BLVD & GALLEY RD", "city": "COLORADO SPRINGS",
           "location_point": {"type": "Point", "coordinates": [-104.7601, 38.8502]}}
    row.update(extra)
    return row


def test_registered():
    assert records.all_specs()["colorado_springs"] is cs.SPEC


def test_parse():
    record = cs.parse(cs_row())
    assert record["crash_datetime"] == datetime(2026, 11, 9, 16, 45)
    assert (record["latitude"], record["longitude"]) == (38.8502, -104.7601)  # GeoJSON is [lon, lat]
    assert record["injured"] == 2 and record["killed"] == 0 and record["severity"] == "Injury"
    assert record["primary_cause"] == "FOLLOWED TO CLOSELY" and record["crash_type"] == "Front to Rear"
    assert record["road"] == "N ACADEMY BLVD & GALLEY RD" and record["weather"] is None


def test_coordinates_missing_or_outside():
    assert cs.parse(cs_row(location_point=None))["latitude"] is None
    assert cs.parse(cs_row(location_point={"type": "Point", "coordinates": [-104.30044, 39.03532]}))["latitude"] is None


def test_severity_from_flags():
    assert cs.parse(cs_row(involved_death_="Yes", involved_injury_="No"))["severity"] == "Fatal"
    assert cs.parse(cs_row(involved_injury_="No"))["severity"] == "No injury"
    assert cs.parse(cs_row(involved_death_=None, involved_injury_="No"))["severity"] is None
    assert cs.parse(cs_row(numberofinjured=None))["injured"] is None


def test_repeated_accident_number_kept_once():
    out, skipped = base.parse_all(cs.SPEC, [cs_row(), cs_row(driveraction="CARELESS DRIVING"), cs_row("X")])
    assert len(out) == 2 and skipped == 0
