from datetime import datetime, timedelta

import pytest

from app.models import LiveIncident
from pipeline.live import nj511
from pipeline.live.poller import poll_source

NOW = datetime(2026, 11, 16, 6, 0)

ITEM = """<item>
            <title>{title}</title>
            <description>{description}</description>
            <pubDate>{pub}</pubDate>
            <georss:point>{point}</georss:point>
        </item>"""


def item(title="I-80 - NJ Turnpike eastbound : Crash",
         description="NJ DOT - STMC: crash on I-80 eastbound at Exit 99 (Sampleville), left lane closed",
         pub="Mon, 16 Nov 2026 00:30:00 -0500", point="40.9 -74.1"):
    return ITEM.format(title=title, description=description, pub=pub, point=point)


def feed(*items):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<rss version="2.0" xmlns:georss="http://www.georss.org/georss" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <title>Active Incidents</title>
        <description>All Active Incidents</description>
        <pubDate>Mon, 16 Nov 2026 00:54:05 -0500</pubDate>
        <atom:link type="application/rss+xml" rel="self" href="TRANSCOMRSSActiveIncidents"/>
        {"".join(items)}
    </channel>
</rss>"""


def parsed(*items):
    return [nj511.parse(raw) for raw in nj511.fetch(None, lambda url: feed(*items))]


def test_nj511_categories_cover_real_titles():
    titles = {"I-90 - NYS Thruway eastbound : Crash": "crash", "I-684 southbound : Disabled vehicle": "stalled_vehicle",
              "I-287 northbound : Fuel spill": "hazard", "I-87 - NYS Thruway northbound : Roving repairs": "other",
              "I-495 westbound : Roadwork": "other", "NY 28 both directions : Rough road": "other",
              "Port Street both directions : Truck restrictions": "other", "Main St both directions : Road closed": "closure",
              "US 9 southbound : Vehicle fire": "fire", "Route 4 eastbound : Accident": "crash", "NJ 17 northbound : Debris": "hazard"}
    assert {title: nj511.classify(title, None) for title in titles} == titles
    # a vague title falls back to the description's lead phrase, but never on place names or lane notes
    assert nj511.classify("I-87 northbound : Incident", "NYSTA - Statewide Ops.: crash ,left lane blocked on I-87") == "crash"
    assert nj511.classify("NY 27 eastbound : Roadwork", "NYSDOT - Region 10: Roadwork on NY 27 to Fire Island, lanes closed") == "other"


def test_nj511_parse():
    [record] = parsed(item(description="NYSTA - Statewide Ops.: crash on I-90 [CARS CAD-263200008]"))
    assert record["category"] == "crash" and record["raw_type"] == "Crash" and record["status"] == "active"
    assert record["road"] == "I-80 - NJ Turnpike" and (record["latitude"], record["longitude"]) == (40.9, -74.1)
    assert record["source_id"] == "cad-263200008"
    assert record["reported_at"] == datetime(2026, 11, 16, 5, 30)  # -0500 converted to naive UTC


def test_nj511_timezones_and_bad_values():
    [edt, utc_z] = parsed(item(pub="Sun, 01 Nov 2026 01:30:00 -0400"), item(pub="Mon, 16 Nov 2026 05:30:00 GMT"))
    assert edt["reported_at"] == datetime(2026, 11, 1, 5, 30) and utc_z["reported_at"] == datetime(2026, 11, 16, 5, 30)
    far, missing = parsed(item(point="34.05 -118.24"), item(point=""))
    assert far["latitude"] is None and missing["longitude"] is None  # outside the NJ/NY/CT/PA box, or absent
    assert parsed(item(pub="not a date")) == [None] and parsed(item(title="")) == [None]


def test_nj511_id_survives_description_updates():
    first = parsed(item(description="NJ DOT - STMC: crash on I-80, 2 left lanes of 3 lanes closed"))[0]
    later = parsed(item(description="NJ DOT - STMC: crash on I-80, left lane closed, delays 2 miles", point="40.90004 -74.10003"))[0]
    other = parsed(item(pub="Mon, 16 Nov 2026 02:10:00 -0500"))[0]
    assert first["source_id"] == later["source_id"] != other["source_id"]
    assert first["source_id"].startswith("h-")


def test_nj511_rejects_dtd():
    with pytest.raises(ValueError):
        nj511.fetch(None, lambda url: '<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY x "y">]><rss/>')


def test_nj511_poll_clears_incidents_missing_from_snapshot(db):
    crash = item()
    stalled = item(title="I-684 southbound : Disabled vehicle", point="41.3 -73.66",
                   description="NYSDOT - Region 8: Disabled Vehicle on I-684 southbound CAD #98050080")
    pages = [feed(crash, stalled), feed(item(description="NJ DOT - STMC: crash on I-80, all lanes open"))]
    urls = []
    def get(url):
        urls.append(url)
        return pages[len(urls) - 1]

    first = poll_source(db, nj511, now=NOW, get=get)
    assert (first.fetched, first.inserted, first.error) == (2, 2, None) and urls == [nj511.URL]
    second = poll_source(db, nj511, now=NOW + timedelta(minutes=5), get=get)
    assert (second.inserted, second.updated, second.cleared) == (0, 1, 1)  # same crash, new text; vehicle gone

    rows = {row.source_id: row for row in db.query(LiveIncident).filter_by(source="nj511")}
    assert rows["cad-98050080"].status == "cleared" and rows["cad-98050080"].cleared_at == NOW + timedelta(minutes=5)
    [crash_row] = [row for sid, row in rows.items() if sid.startswith("h-")]
    assert crash_row.status == "active" and crash_row.description.endswith("all lanes open")
