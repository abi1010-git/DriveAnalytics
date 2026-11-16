from datetime import datetime, timezone

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import denver


def ms(*args):  # Denver stores local wall time as if it were UTC
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def den_row(incident="DP2026631653", when=None, **extra):
    row = {"object_id": 1, "incident_id": incident, "offense_id": incident + "54410", "offense_code": "5441",
           "top_traffic_accident_offense": "TRAF - ACCIDENT               ",
           "first_occurrence_date": ms(2026, 11, 11, 19, 30) if when is None else when,
           "reported_date": ms(2026, 11, 11, 19, 38), "incident_address": "903 S FEDERAL BLVD",
           "geo_lat": 39.70034009, "geo_lon": -105.02527878, "HARMFUL_EVENT_SEQ_1": "FRONT TO REAR",
           "LIGHT_CONDITION": "DARK-LIGHTED", "TU1_DRIVER_HUMANCONTRIBFACTOR": "DISTRACTED",
           "SERIOUSLY_INJURED": 0, "FATALITIES": 0, "_lon": -105.0252788, "_lat": 39.7003401}
    row.update(extra)
    return row


def test_registered():
    spec = records.all_specs()["denver"]
    assert spec is denver.SPEC and spec.epoch_is_local and spec.reduce is denver.reduce


def test_parse_local_wall_time():
    record = denver.parse(den_row())
    assert record["source_id"] == "DP2026631653"
    assert record["crash_datetime"] == datetime(2026, 11, 11, 19, 30)  # stored value is already local
    assert record["severity"] == "TRAF - ACCIDENT" and record["hit_and_run"] is None
    assert record["injured"] == 0 and record["killed"] == 0
    assert record["lighting"] == "DARK-LIGHTED" and record["crash_type"] == "FRONT TO REAR"
    assert record["primary_cause"] == "DISTRACTED" and record["road"] == "903 S FEDERAL BLVD"


def test_labels_and_missing_counts():
    hit_run = denver.parse(den_row(top_traffic_accident_offense="TRAF - ACCIDENT - HIT & RUN   ",
                                   SERIOUSLY_INJURED=None, FATALITIES=None))
    assert hit_run["hit_and_run"] is True and hit_run["injured"] is None and hit_run["killed"] is None
    fatal = denver.parse(den_row(top_traffic_accident_offense="TRAF - ACCIDENT - FATAL", SERIOUSLY_INJURED=2, FATALITIES=1))
    assert fatal["severity"] == "TRAF - ACCIDENT - FATAL" and fatal["injured"] == 2 and fatal["killed"] == 1


def test_coordinates():
    assert denver.parse(den_row(geo_lat=None, geo_lon=None))["latitude"] == 39.7003401  # geometry fallback
    assert denver.parse(den_row(geo_lat=None, geo_lon=None, _lat=None, _lon=None))["latitude"] is None
    assert denver.parse(den_row(geo_lat=40.0, geo_lon=-105.27, _lat=None, _lon=None))["latitude"] is None  # Boulder


def test_reduce_merges_offense_rows_of_one_incident():
    rows = [den_row("2021590648", top_traffic_accident_offense="TRAF - ACCIDENT - SBI", SERIOUSLY_INJURED=None,
                    FATALITIES=None, LIGHT_CONDITION=None),
            den_row("2021590648", top_traffic_accident_offense="TRAF - ACCIDENT - SBI", SERIOUSLY_INJURED=1,
                    FATALITIES=0),
            den_row("2021590648", top_traffic_accident_offense="TRAF - ACCIDENT - SBI", SERIOUSLY_INJURED=1,
                    FATALITIES=0),
            den_row("OTHER")]
    merged, skipped = base.parse_all(denver.SPEC, rows)
    assert skipped == 0 and len(merged) == 2
    one = next(r for r in merged if r["source_id"] == "2021590648")
    assert one["injured"] == 1 and one["killed"] == 0  # max of repeated counts, not a sum
    assert one["lighting"] == "DARK-LIGHTED" and one["severity"] == "TRAF - ACCIDENT - SBI"


def test_reduce_keeps_hit_and_run():
    rows = [denver.parse(den_row()), denver.parse(den_row(top_traffic_accident_offense="TRAF - ACCIDENT - HIT & RUN"))]
    assert denver.reduce(rows)["hit_and_run"] is True
