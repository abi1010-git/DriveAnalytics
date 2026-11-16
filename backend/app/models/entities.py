"""Database tables for real crash records.

Two sources are stored side by side instead of being forced into one schema:
FARS covers every fatal crash in the US (about 35-40k a year), while NYC Open Data
covers every police-reported crash in New York City (about 2.3M since 2012). Their
fields differ too much for one table to be honest about either.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class FarsCrash(Base):
    """One row per fatal crash from the NHTSA FARS ACCIDENT file, plus vehicle-level rollups."""

    __tablename__ = "fars_crashes"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "{year}-{ST_CASE}"; ST_CASE is only unique within a year
    year: Mapped[int] = mapped_column(Integer, index=True)
    st_case: Mapped[int] = mapped_column(Integer)
    state_code: Mapped[int] = mapped_column(Integer, index=True)
    state_name: Mapped[str | None] = mapped_column(String(40))
    county_code: Mapped[int | None] = mapped_column(Integer)
    county_name: Mapped[str | None] = mapped_column(Text)
    city_name: Mapped[str | None] = mapped_column(Text)
    crash_date: Mapped[date | None] = mapped_column(Date, index=True)
    hour: Mapped[int | None] = mapped_column(Integer)
    minute: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    fatalities: Mapped[int] = mapped_column(Integer)
    persons: Mapped[int | None] = mapped_column(Integer)
    pedestrians: Mapped[int | None] = mapped_column(Integer)
    vehicles: Mapped[int | None] = mapped_column(Integer)
    weather_code: Mapped[int | None] = mapped_column(Integer)
    weather: Mapped[str | None] = mapped_column(Text)
    light_code: Mapped[int | None] = mapped_column(Integer)
    light_condition: Mapped[str | None] = mapped_column(Text)
    junction_code: Mapped[int | None] = mapped_column(Integer)
    junction: Mapped[str | None] = mapped_column(Text)
    intersection_type: Mapped[str | None] = mapped_column(Text)
    rural_urban: Mapped[str | None] = mapped_column(Text)
    road_class: Mapped[str | None] = mapped_column(Text)
    road_name: Mapped[str | None] = mapped_column(Text)
    road_route: Mapped[str | None] = mapped_column(Text, index=True)  # normalized key, e.g. "I-45" for "I-45/GULF FWY"
    cross_road_name: Mapped[str | None] = mapped_column(Text)
    first_harmful_event: Mapped[str | None] = mapped_column(Text)
    collision_manner: Mapped[str | None] = mapped_column(Text)
    speeding_involved: Mapped[bool] = mapped_column(Boolean, default=False)
    drinking_driver_involved: Mapped[bool] = mapped_column(Boolean, default=False)
    max_speed_limit_mph: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_fars_crashes_lat_lon", "latitude", "longitude"),)


class NycCrash(Base):
    """One row per crash from NYC Open Data "Motor Vehicle Collisions - Crashes" (h9gi-nx95)."""

    __tablename__ = "nyc_crashes"
    collision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    crash_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    hour: Mapped[int | None] = mapped_column(Integer)
    borough: Mapped[str | None] = mapped_column(String(20), index=True)
    zip_code: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    on_street: Mapped[str | None] = mapped_column(Text)
    cross_street: Mapped[str | None] = mapped_column(Text)
    off_street: Mapped[str | None] = mapped_column(Text)
    persons_injured: Mapped[int] = mapped_column(Integer, default=0)
    persons_killed: Mapped[int] = mapped_column(Integer, default=0)
    pedestrians_injured: Mapped[int] = mapped_column(Integer, default=0)
    pedestrians_killed: Mapped[int] = mapped_column(Integer, default=0)
    cyclists_injured: Mapped[int] = mapped_column(Integer, default=0)
    cyclists_killed: Mapped[int] = mapped_column(Integer, default=0)
    motorists_injured: Mapped[int] = mapped_column(Integer, default=0)
    motorists_killed: Mapped[int] = mapped_column(Integer, default=0)
    vehicle_types: Mapped[list] = mapped_column(JSON, default=list)

    __table_args__ = (Index("ix_nyc_crashes_lat_lon", "latitude", "longitude"),)


class NycCrashFactor(Base):
    """Contributing factors (one per vehicle, up to five) kept in their own table so "why" queries can GROUP BY."""

    __tablename__ = "nyc_crash_factors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collision_id: Mapped[str] = mapped_column(ForeignKey("nyc_crashes.collision_id", ondelete="CASCADE"), index=True)
    vehicle_number: Mapped[int] = mapped_column(Integer)
    factor: Mapped[str] = mapped_column(Text, index=True)


class CrashFlag(Base):
    """A risk-factor flag from config/risk_flags.yaml that matched a crash."""

    __tablename__ = "crash_flags"
    source: Mapped[str] = mapped_column(String(8), primary_key=True)  # "fars" or "nyc"
    crash_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    flag_id: Mapped[str] = mapped_column(String(60), primary_key=True, index=True)


class IngestRun(Base):
    """Provenance: what was loaded, from where, and when."""

    __tablename__ = "ingest_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(60))
    source_url: Mapped[str] = mapped_column(Text)
    rows_loaded: Mapped[int] = mapped_column(Integer)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime)


class LiveIncident(Base):
    """A traffic incident from a live feed (city dispatch data, state 511 systems).

    These are reports, not verified crash records: they arrive within minutes but carry
    no injury counts or causes, and some turn out to be minor. Rows are never deleted;
    when a feed stops listing an incident it is marked cleared, so history builds up."""

    __tablename__ = "live_incidents"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)  # crash | hazard | stalled_vehicle | closure | fire | other
    raw_type: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    road: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    reported_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC, as given by the source
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | cleared
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)  # when our poller first saw it
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (Index("ix_live_incidents_lat_lon", "latitude", "longitude"),)


class LivePoll(Base):
    """One poll of one live source, so the app can show how fresh each feed is."""

    __tablename__ = "live_polls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    polled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    cleared: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class LocalCrash(Base):
    """Police crash *records* from city or state open-data portals other than NYC (e.g. Chicago).

    Unlike live incidents these are filed reports with injury counts and causes, published
    days to weeks after the crash. Each portal has its own loader in pipeline/ that maps its
    fields onto these columns; anything that doesn't fit stays out rather than being guessed.
    """

    __tablename__ = "local_crashes"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g. "chicago"
    source_id: Mapped[str] = mapped_column(String(160), primary_key=True)  # Chicago ids are 128 chars
    crash_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)  # local time of the city, as published
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    road: Mapped[str | None] = mapped_column(Text)  # street, e.g. "W 63RD ST" or "4400 S KEDZIE AVE"
    injured: Mapped[int | None] = mapped_column(Integer)  # None when the source doesn't say
    killed: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str | None] = mapped_column(Text)  # the source's own severity label, e.g. "INCAPACITATING INJURY"
    primary_cause: Mapped[str | None] = mapped_column(Text)
    weather: Mapped[str | None] = mapped_column(Text)
    lighting: Mapped[str | None] = mapped_column(Text)
    crash_type: Mapped[str | None] = mapped_column(Text)  # e.g. "REAR END", "PEDESTRIAN"
    hit_and_run: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (Index("ix_local_crashes_lat_lon", "latitude", "longitude"),)
