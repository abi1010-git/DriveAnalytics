from datetime import datetime

from pipeline import records
from pipeline.records import base
from pipeline.records.sources import cincinnati as cin


def cin_row(rid="265000001", injuries="5 - No Apparent Injury", **extra):
    row = {"reportdate": "2026-11-10T19:21:00.000", "eventdate": "2026-11-10T17:21:00.000", "reportnumber": rid,
           "latitude": "39.1301", "longitude": "-84.5102", "mannerofcrash": "Rear End", "weather": "Clear",
           "lightconditionsprimary": "Daylight", "address": "1500 Vine St", "crashseverity": "Minor Injury Suspected",
           "unitno": "1", "typeofperson": "D - Driver", "injuries": injuries}
    row.update(extra)
    return row


def test_registered():
    assert records.all_specs()["cincinnati"] is cin.SPEC


def test_parse_uses_event_time():
    record = cin.parse(cin_row())
    assert record["crash_datetime"] == datetime(2026, 11, 10, 17, 21)
    assert (record["latitude"], record["longitude"]) == (39.1301, -84.5102)
    assert record["severity"] == "Minor Injury Suspected" and record["road"] == "1500 Vine St"
    assert record["crash_type"] == "Rear End" and record["lighting"] == "Daylight"
    assert cin.parse(cin_row(eventdate=None))["crash_datetime"] is None
    assert cin.parse(cin_row(eventdate="1900-02-06T00:00:00.000"))["crash_datetime"] is None
    assert cin.parse(cin_row(latitude="842432889.0"))["latitude"] is None


def test_person_outcome_both_code_lists():
    assert cin.person_outcome("1 - Fatal") == (0, 1) and cin.person_outcome("5 - Fatal") == (0, 1)
    for label in ("2 - Possible", "3 - Non-incapacitating", "4 - Incapacitating", "2 - Suspected Serious Injury",
                  "3 - Suspected Minor Injury", "4 - Possible Injury"):
        assert cin.person_outcome(label) == (1, 0)
    for label in ("1 - No Injury / None Reported", "5 - No Apparent Injury", "5 - No Apparenty Injury"):
        assert cin.person_outcome(label) == (0, 0)
    assert cin.person_outcome("Not Applicable or Unknown") == (None, None) and cin.person_outcome(None) == (None, None)


def test_reduce_counts_people_per_report():
    rows = [cin_row("A", "5 - No Apparenty Injury"), cin_row("A", "3 - Suspected Minor Injury", unitno="2"),
            cin_row("A", "4 - Possible Injury", typeofperson="O - Occupant"), cin_row("A", "1 - Fatal"),
            cin_row("B", "1 - No Injury / None Reported"),
            cin_row("C", "Not Applicable or Unknown"), cin_row("C", None)]
    out, skipped = base.parse_all(cin.SPEC, rows)
    by_id = {r["source_id"]: r for r in out}
    assert skipped == 0 and len(out) == 3
    assert (by_id["A"]["injured"], by_id["A"]["killed"]) == (2, 1)
    assert (by_id["B"]["injured"], by_id["B"]["killed"]) == (0, 0)  # single row, no reduce
    assert (by_id["C"]["injured"], by_id["C"]["killed"]) == (None, None)
    assert by_id["A"]["crash_datetime"] == datetime(2026, 11, 10, 17, 21)
