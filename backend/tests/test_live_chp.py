from datetime import datetime, timedelta

import pytest

from app.models import LiveIncident
from pipeline.live import chp
from pipeline.live.poller import poll_source

NOW = datetime(2026, 11, 16, 6, 0)


def log(log_id, log_type, time="Nov 15 2026  9:49PM", latlon="38918480:121081135", location="Us50 W / Example Dr",
        desc="WB 50 AT EXAMPLE", area="Placerville", details=()):
    extra = "".join(f'<details>\n\t\t\t<DetailTime>"{t}"</DetailTime>\n\t\t\t<IncidentDetail>"[1] TEST"</IncidentDetail>\n\t\t</details>'
                    for t in details)
    return f'''
		<Log ID = "{log_id}">
			<LogTime>"{time}"</LogTime>
			<LogType>"{log_type}"</LogType>
			<Location>"{location}"</Location>
			<LocationDesc>"{desc}"</LocationDesc>
			<Area>"{area}"</Area>
			<ThomasBrothers>""</ThomasBrothers>
			<LATLON>"{latlon}"</LATLON>
			<LogDetails>{extra}<units>
			<UnitTime>"{time}"</UnitTime>
			<UnitDetail>"Unit Assigned"</UnitDetail></units></LogDetails></Log>
'''


def feed(*dispatches):
    """dispatches: (center_id, dispatch_id, [log xml, ...])"""
    body = "".join(f'<Center ID = "{c}">\n<Dispatch ID = "{d}">\n{"".join(logs)}</Dispatch></Center>' for c, d, logs in dispatches)
    return f'<?xml version="1.0" ?>\n<State>{body}</State>'


FEED = feed(("SAHB", "SACC", [log("261115SA0001", "1183-Trfc Collision-Unkn Inj", details=["Nov 15 2026  9:53PM"]),
                              log("261115SA0002", "1125-Traffic Hazard", latlon="0:0")]),
            ("GGHB", "GGCC", [log("261115SA0001", "CLOSURE of a Road", location="E Cliff Dr / 26th Ave", desc="", area="Santa Cruz")]))


def test_chp_categories_cover_real_labels():
    labels = {"1182-Trfc Collision-No Inj": "crash", "1179-Trfc Collision-1141 Enrt": "crash", "1183-Trfc Collision-Unkn Inj": "crash",
              "1181-Trfc Collision-Minor Inj": "crash", "20002-Hit and Run No Injuries": "crash",
              "1125-Traffic Hazard": "hazard", "1125A-Animal Hazard": "hazard", "FLOOD-Roadway Flooding": "hazard", "SPINOUT": "hazard",
              "CLOSURE of a Road": "closure", "CFIRE-Car Fire": "fire", "FIRE-Report of Fire": "fire",
              "1125V-Disabled Vehicle": "stalled_vehicle", "CZP-Assist with Construction": "other", "FOG-Foggy Conditions": "other",
              "SILVER-Missing Elderly": "other", "1013-Road/Weather Conditions": "other", None: "other"}
    assert {label: chp.category(label) for label in labels} == labels


def test_chp_parse_and_unique_ids():
    records = [chp.parse(raw) for raw in chp.fetch(None, lambda url: FEED)]
    assert [r["source_id"] for r in records] == ["SACC-261115SA0001", "SACC-261115SA0002", "GGCC-261115SA0001"]
    crash, hazard, closure = records
    assert crash["category"] == "crash" and crash["raw_type"] == "1183-Trfc Collision-Unkn Inj" and crash["status"] == "active"
    assert (crash["latitude"], crash["longitude"]) == (38.91848, -121.081135)  # longitude sign restored
    assert crash["road"] == "Us50 W / Example Dr" and crash["description"] == "WB 50 AT EXAMPLE - Placerville"
    assert crash["reported_at"] == datetime(2026, 11, 16, 5, 49)  # 9:49 PM PST = UTC-8
    assert crash["updated_at"] == datetime(2026, 11, 16, 5, 53)  # newest detail time
    assert hazard["latitude"] is None and hazard["longitude"] is None  # "0:0" means no position
    assert closure["category"] == "closure" and closure["description"] == "Santa Cruz"


def test_chp_rejects_out_of_state_and_bad_records():
    nevada = chp.records(feed(("INHB", "BSCC", [log("1", "SPINOUT", latlon="39500000:119800000")])))[0]
    nevada["LATLON"] = "39500000:114000000"  # east of California
    assert chp.parse(nevada)["latitude"] is None
    assert chp.parse({**nevada, "LogTime": "garbage"}) is None and chp.parse({**nevada, "log_id": None}) is None


@pytest.mark.parametrize("local, expected", [
    ("Jul 4 2026 12:00PM", datetime(2026, 7, 4, 19, 0)),      # PDT, UTC-7
    ("Jan 15 2026 11:30PM", datetime(2026, 1, 16, 7, 30)),    # PST, UTC-8, crosses midnight
    ("Mar 8 2026  3:00AM", datetime(2026, 3, 8, 10, 0)),      # first PDT hour
    ("Mar 8 2026  1:59AM", datetime(2026, 3, 8, 9, 59)),      # last PST minute
    ("Nov 1 2026  2:00AM", datetime(2026, 11, 1, 10, 0)),     # back on PST
])
def test_chp_pacific_to_utc(local, expected):
    assert chp.parse_time(local) == expected



def test_chp_poll_clears_incidents_that_leave_the_feed(db):
    snapshots = [FEED, feed(("SAHB", "SACC", [log("261115SA0001", "1183-Trfc Collision-Unkn Inj", details=["Nov 15 2026  9:53PM"])]))]
    urls = []
    def get(url):
        urls.append(url)
        return snapshots[len(urls) - 1]

    first = poll_source(db, chp, now=NOW, get=get)
    assert (first.fetched, first.inserted, first.error) == (3, 3, None) and urls == [chp.URL]
    second = poll_source(db, chp, now=NOW + timedelta(minutes=5), get=get)
    assert (second.fetched, second.inserted, second.updated, second.cleared) == (1, 0, 0, 2)
    assert db.get(LiveIncident, ("chp", "SACC-261115SA0001")).status == "active"
    gone = db.get(LiveIncident, ("chp", "GGCC-261115SA0001"))
    assert (gone.status, gone.cleared_at) == ("cleared", NOW + timedelta(minutes=5))


def test_chp_retries_a_half_written_file(monkeypatch):
    import xml.etree.ElementTree as ET

    import pytest
    monkeypatch.setattr(chp, "RETRY_DELAY", 0)
    full = '<State><Center ID="SAHB"><Dispatch ID="SACC"></Dispatch></Center></State>'
    replies = iter([full[:30], full])
    assert chp.fetch(None, lambda url: next(replies)) == []
    with pytest.raises(ET.ParseError):
        chp.fetch(None, lambda url: full[:30])
