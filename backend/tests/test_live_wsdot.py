from datetime import datetime, timedelta

from app.models import LiveIncident
from pipeline.live import wsdot
from pipeline.live.poller import poll_source

NOW = datetime(2026, 11, 16, 6, 0)


def placemark(aid, style, text, coords="-122.30,47.40"):
    point = f"<Point><coordinates>{coords}</coordinates></Point>" if coords else ""
    return (f'<Placemark id="ID {aid}"><name><![CDATA[{text}]]></name><description><![CDATA[<div>High Impact</div>'
            f"<div>{text}</div><div></div>]]></description><styleUrl>#{style}</styleUrl>{point}</Placemark>")


def kml(*marks):
    return ('﻿<kml xmlns="http://www.opengis.net/kml/2.2"><Document><LookAt id="WA"><longitude>-120.94</longitude>'
            '<latitude>47.33</latitude></LookAt><Style id="HighestCollision"><IconStyle><scale>1</scale></IconStyle></Style>'
            + "".join(marks) + "</Document></kml>")


def rss(*items):
    body = "".join(f'<item><guid isPermaLink="false">{aid}</guid><link>http://www.wsdot.wa.gov/traffic/trafficalerts/default.aspx?'
                   f"refnum={aid}&amp;action=2</link><title>Alert {aid}</title><description>&lt;div&gt;High Impact&lt;/div&gt;"
                   f"</description><a10:updated>{stamp}</a10:updated></item>" for aid, stamp in items)
    return ('<?xml version="1.0" encoding="us-ascii"?><rss xmlns:a10="http://www.w3.org/2005/Atom" version="2.0"><channel>'
            f"<title>WA State Highway Alerts</title>{body}</channel></rss>")


COLLISION = placemark(900001, "HighestCollision", "Collision on SR 7 both directions at milepost 49.1 near 160th St S. "
                      'Expect delays. <a href="https://example.org">More</a>')
STALL = placemark(900002, "MediumDisabledvehicle", "Disabled vehicle on I-5 southbound at milepost 120.", coords="0,0")


def feeds(marks, items):
    pages = {wsdot.KML_URL: kml(*marks), wsdot.RSS_URL: rss(*items)}
    return lambda url: pages[url]


def test_wsdot_categories_cover_real_styles():
    cases = {("HighestCollision", ""): "crash", ("HighCollisionfatality", ""): "crash", ("LowRollover", ""): "crash",
             ("MediumDisabledvehicle", ""): "stalled_vehicle", ("HighestTreesdown", "Trees down on US 101"): "hazard",
             ("LowDeadAnimal", ""): "hazard", ("HighVehiclefire", ""): "fire", ("HighestClosure", ""): "closure",
             ("HighestConstruction", "SR 116 is closed to all travelers between A and B."): "closure",
             ("MediumConstruction", "The southbound I-5 off-ramp to Mercer Street will be closed from 10 p.m."): "closure",
             ("HighConstruction", "All lanes of northbound I-405 will be closed nightly."): "closure",
             ("MediumConstruction", "The right lane of northbound I-5 is closed from A to B."): "other",
             ("LowConstruction", "Northbound and southbound SR 9 traffic will alternate from 10 a.m."): "other",
             ("LowLaneClosure", "Shoulder Closure on I-90 eastbound near MP 273."): "other",
             ("HighestRestArea", "The SR 401 rest area is closed."): "other",
             ("HighIncident", "I-90 Exit 154 overpass: the overpass is closed due to a hole in the bridge deck."): "closure",
             ("HighestIncident", "On I-5 northbound there is an incident blocking the 2 right lanes."): "other",
             ("HighestIncident", "Collision blocking the left lane."): "crash", (None, None): "other"}
    assert {key: wsdot.category(*key) for key in cases} == cases


def test_wsdot_road_names():
    assert wsdot.road("Collision on SR 7 both directions near I-5") == "SR 7"
    assert wsdot.road("Effective Oct. 25, State Route 542/Road to Artist Point has closed") == "SR 542"
    assert wsdot.road("Westbound Interstate 90 is open to two lanes") == "I-90"
    assert wsdot.road("The Horn School rest area on US195 at milepost 60.5") == "US 195"
    assert wsdot.road("Lane closures on Sullivan Rd in Spokane Valley") is None


def test_wsdot_fetch_joins_feeds_and_parses():
    rows = wsdot.fetch(None, feeds([COLLISION, STALL], [("900001", "2026-11-15T20:31:02-08:00"),
                                                        ("900002", "2026-07-01T09:00:00-07:00")]))
    crash, stall = [wsdot.parse(row) for row in rows]
    assert crash["source_id"] == "900001" and crash["category"] == "crash" and crash["raw_type"] == "Collision"
    assert crash["reported_at"] == crash["updated_at"] == datetime(2026, 11, 16, 4, 31, 2)  # PST -> UTC
    assert stall["reported_at"] == datetime(2026, 7, 1, 16, 0)  # PDT -> UTC
    assert (crash["latitude"], crash["longitude"], crash["road"]) == (47.40, -122.30, "SR 7")
    assert crash["description"].startswith("Highest impact: Collision on SR 7") and "<a" not in crash["description"]
    assert stall["category"] == "stalled_vehicle" and stall["latitude"] is None and stall["road"] == "I-5"
    assert crash["status"] == "active"


def test_wsdot_skips_alerts_without_id_or_time():
    rows = wsdot.fetch(None, feeds([COLLISION, placemark("", "HighCollision", "x")], []))
    assert [wsdot.parse(row) for row in rows] == [None, None]  # no RSS time for 900001, no id for the other


def test_wsdot_poll_clears_alerts_no_longer_listed(db):
    polls = [feeds([COLLISION, STALL], [("900001", "2026-11-15T20:31:02-08:00"), ("900002", "2026-11-15T20:00:00-08:00")]),
             feeds([STALL], [("900002", "2026-11-15T20:10:00-08:00")])]
    calls = []
    def get(url):
        calls.append(url)
        return polls[(len(calls) - 1) // 2](url)  # each poll reads both feeds

    first = poll_source(db, wsdot, now=NOW, get=get)
    assert (first.fetched, first.inserted, first.error) == (2, 2, None)
    second = poll_source(db, wsdot, now=NOW + timedelta(minutes=10), get=get)
    assert (second.fetched, second.updated, second.cleared) == (1, 1, 1)
    crash, stall = db.get(LiveIncident, ("wsdot", "900001")), db.get(LiveIncident, ("wsdot", "900002"))
    assert (crash.status, crash.cleared_at) == ("cleared", NOW + timedelta(minutes=10))
    assert stall.status == "active" and stall.updated_at == datetime(2026, 11, 16, 4, 10)
