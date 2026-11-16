from datetime import datetime

from pipeline.records.sources import somerville_ma as som


def som_row(num="26074086", when="2026-10-14 16:21:00", **extra):
    row = {"crashnum": num, "dtcrash": when, "address": "HIGHLAND AV & SYCAMORE ST Somerville, MA",
           "ambntlightdesc": "DAYLIGHT                 ", "weathcond1desc": "CLEAR            ",
           "manrcolldesc": "REAR-END            ", "fatalinjury": "0", "suspectedseriousinjury": "0",
           "suspectedminorinjury": "0", "possibleinjury": "1", "noapparentinjury": "2", "unknown": "0",
           "notreported": "0", "hitrunflag": "N", "latitude": "42.3879", "longitude": "-71.1019"}
    row.update(extra)
    return row


def test_parse_fields_and_coordinates():
    record = som.parse(som_row())
    assert record["source_id"] == "26074086" and record["road"] == "HIGHLAND AV & SYCAMORE ST"
    assert record["latitude"] == 42.3879 and record["longitude"] == -71.1019
    assert record["crash_type"] == "REAR-END" and record["weather"] == "CLEAR" and record["lighting"] == "DAYLIGHT"
    assert record["hit_and_run"] is False and som.parse(som_row(hitrunflag="Y"))["hit_and_run"] is True
    assert som.parse(som_row(latitude="", longitude=""))["latitude"] is None
    assert som.parse(som_row(latitude="42.39", longitude="71.10"))["longitude"] is None


def test_counts_and_severity():
    record = som.parse(som_row())
    assert record["injured"] == 1 and record["killed"] == 0 and record["severity"] == "Possible Injury"
    worst = som.parse(som_row(fatalinjury="1", suspectedseriousinjury="2", suspectedminorinjury="1"))
    assert worst["severity"] == "Fatal Injury" and worst["killed"] == 1 and worst["injured"] == 4
    assert som.parse(som_row(possibleinjury="0"))["severity"] == "No Apparent Injury"
    assert som.parse(som_row(possibleinjury="0", noapparentinjury="0", unknown="3"))["severity"] is None
    assert som.parse(som_row(possibleinjury=None))["injured"] is None


def test_text_dates_parse():
    assert som.parse(som_row())["crash_datetime"] == datetime(2026, 10, 14, 16, 21)
    assert som.parse(som_row(when="2019-05-02"))["crash_datetime"] == datetime(2019, 5, 2)
    assert som.parse(som_row(when="10/14/2026 4:21 PM"))["crash_datetime"] == datetime(2026, 10, 14, 16, 21)
    assert som.parse(som_row(when="2026-10-14T16:21:00.000"))["crash_datetime"] == datetime(2026, 10, 14, 16, 21)
    assert som.parse(som_row(when="garbage"))["crash_datetime"] is None
    assert som.parse(som_row(when=None))["crash_datetime"] is None


def test_id_stable():
    assert som.parse(som_row(possibleinjury="0"))["source_id"] == som.parse(som_row())["source_id"]
    assert som.parse(som_row(num=" 1800000018 "))["source_id"] == "1800000018"
