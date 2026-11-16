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
    source: Mapped[str] = mapped_column(String(8), index=True)
    scope: Mapped[str] = mapped_column(String(60))
    source_url: Mapped[str] = mapped_column(Text)
    rows_loaded: Mapped[int] = mapped_column(Integer)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
