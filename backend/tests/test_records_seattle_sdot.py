from datetime import datetime, timezone

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import seattle_sdot as sdot


def ms(*args):
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def sdot_row(inckey=395016, text="11/7/2026 8:55:00 PM", **extra):
    row = {"OBJECTID": 1, "INCKEY": inckey, "COLDETKEY": 396556, "REPORTNO": "3926502", "STATUS": "Unmatched",
           "LOCATION": "4TH AVE AND PIKE ST", "INCDATE": ms(2026, 11, 7, 8), "INCDTTM": text, "INJURIES": 2,
           "SERIOUSINJURIES": 1, "FATALITIES": 0, "MAXSEVERITYDESC": "Serious Injury Collision",
           "WEATHER": "Raining", "LIGHTCOND": "Dark - Street Lights On", "ST_COLLISIONTYPE": None,
           "SDOT_COLDESC": "MOTOR VEHCILE STRUCK PEDESTRIAN", "_lon": -122.33668, "_lat": 47.61021}
    row.update(extra)
    return row


def test_registered_separately_from_live_feed():
    assert records.all_specs()["seattle_sdot"] is sdot.SPEC and sdot.SPEC.source != "seattle"


def test_parse():
    record = sdot.parse(sdot_row())
    assert record["source_id"] == "395016" and record["crash_datetime"] == datetime(2026, 11, 7, 20, 55)
    assert record["injured"] == 2 and record["killed"] == 0  # INJURIES already includes SERIOUSINJURIES
    assert record["severity"] == "Serious Injury Collision" and record["road"] == "4TH AVE AND PIKE ST"
    assert record["weather"] == "Raining" and record["lighting"] == "Dark - Street Lights On"
    assert record["crash_type"] == "MOTOR VEHCILE STRUCK PEDESTRIAN"
    assert sdot.parse(sdot_row(ST_COLLISIONTYPE="Angles"))["crash_type"] == "Angles"


def test_time_text_and_fallbacks():
    assert sdot.parse(sdot_row(text="10/31/2026 1:29:00 AM"))["crash_datetime"] == datetime(2026, 10, 31, 1, 29)
    assert sdot.parse(sdot_row(text="12/1/2015 12:05:00 PM"))["crash_datetime"] == datetime(2015, 12, 1, 12, 5)
    assert sdot.parse(sdot_row(text="11/3/2026"))["crash_datetime"] == datetime(2026, 11, 3)
    # no text: INCDATE is local midnight in true UTC (08:00 UTC in PST, 07:00 UTC in PDT)
    assert sdot.parse(sdot_row(text=None))["crash_datetime"] == datetime(2026, 11, 7)
    assert sdot.parse(sdot_row(text="", INCDATE=ms(2015, 7, 1, 7)))["crash_datetime"] == datetime(2015, 7, 1)
    _, skipped = base.parse_all(sdot.SPEC, [sdot_row(text=None, INCDATE=None), sdot_row(INCKEY=None)])
    assert skipped == 2


def test_coordinates_from_geometry_only():
    assert sdot.parse(sdot_row())["latitude"] == 47.61021
    assert sdot.parse(sdot_row(_lat=None, _lon=None))["latitude"] is None
    assert sdot.parse(sdot_row(_lat=47.25, _lon=-122.44))["latitude"] is None  # Tacoma: outside bbox
