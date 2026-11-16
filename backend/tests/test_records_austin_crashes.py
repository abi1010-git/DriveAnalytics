from datetime import datetime

from pipeline import records
from pipeline.records.sources import austin_crashes as ac


def ac_row(cid="21700001", **extra):
    row = {"id": "1800001", "cris_crash_id": cid, "crash_fatal_fl": False, "latitude": "30.2671234",
           "longitude": "-97.7431234", "crash_sev_id": "3", "sus_serious_injry_cnt": "0", "nonincap_injry_cnt": "1",
           "poss_injry_cnt": "1", "tot_injry_cnt": "2", "death_cnt": "0", "address_display": "CONGRESS AVE & 6TH ST",
           "collsn_desc": "SAME DIRECTION - BOTH GOING STRAIGHT-REAR END",
           "crash_timestamp": "2026-07-01T05:13:00.000", "crash_timestamp_ct": "2026-07-01T00:13:00.000",
           "is_deleted": False, "is_temp_record": False}
    row.update(extra)
    return row


def test_registered_separately_from_live_feed():
    specs = records.all_specs()
    assert specs["austin_crashes"] is ac.SPEC and ac.SPEC.date_field == "crash_timestamp_ct"


def test_parse_uses_central_time_not_utc():
    record = ac.parse(ac_row())
    assert record["crash_datetime"] == datetime(2026, 7, 1, 0, 13)
    assert record["source_id"] == "21700001"
    assert (record["latitude"], record["longitude"]) == (30.2671234, -97.7431234)
    assert record["road"] == "CONGRESS AVE & 6TH ST" and record["crash_type"].endswith("REAR END")


def test_counts_and_severity_labels():
    record = ac.parse(ac_row())
    assert record["injured"] == 2 and record["killed"] == 0 and record["severity"] == "POSSIBLE INJURY"
    fatal = ac.parse(ac_row(crash_sev_id="4", death_cnt="1", tot_injry_cnt="0"))
    assert fatal["severity"] == "KILLED" and fatal["killed"] == 1
    assert ac.parse(ac_row(crash_sev_id="0"))["severity"] == "UNKNOWN"
    assert ac.parse(ac_row(crash_sev_id=None))["severity"] is None


def test_skips_deleted_temp_and_bad_coordinates():
    assert ac.parse(ac_row(is_deleted=True)) is None
    assert ac.parse(ac_row(cris_crash_id=None, is_temp_record=True)) is None
    assert ac.parse(ac_row(latitude=None, longitude=None))["latitude"] is None
    assert ac.parse(ac_row(latitude="0", longitude="0"))["longitude"] is None
