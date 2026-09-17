from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_name: Mapped[str] = mapped_column(String(80), unique=True)
    software_version: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20))
    telemetry = relationship("Telemetry", back_populates="vehicle")
    events = relationship("SafetyEvent", back_populates="vehicle")

class Telemetry(Base):
    __tablename__ = "telemetry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    speed_mph: Mapped[float] = mapped_column(Float)
    acceleration_mps2: Mapped[float] = mapped_column(Float)
    steering_angle: Mapped[float] = mapped_column(Float)
    brake_pressure: Mapped[float] = mapped_column(Float)
    battery_percent: Mapped[float] = mapped_column(Float)
    sensor_status: Mapped[str] = mapped_column(String(20))
    route_id: Mapped[str] = mapped_column(String(20), index=True)
    vehicle = relationship("Vehicle", back_populates="telemetry")

class SafetyEvent(Base):
    __tablename__ = "safety_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(Text)
    software_version: Mapped[str] = mapped_column(String(30), index=True)
    route_id: Mapped[str] = mapped_column(String(20), index=True)
    vehicle = relationship("Vehicle", back_populates="events")

class SparkVehicleSummary(Base):
    __tablename__ = "spark_vehicle_summary"
    vehicle_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telemetry_record_count: Mapped[int] = mapped_column(Integer)
    average_speed: Mapped[float] = mapped_column(Float)
    max_speed: Mapped[float] = mapped_column(Float)
    hard_braking_count: Mapped[int] = mapped_column(Integer)
    rapid_acceleration_count: Mapped[int] = mapped_column(Integer)
    sensor_failure_count: Mapped[int] = mapped_column(Integer)

class SparkRouteSummary(Base):
    __tablename__ = "spark_route_summary"
    route_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    telemetry_record_count: Mapped[int] = mapped_column(Integer)
    average_speed: Mapped[float] = mapped_column(Float)
    safety_condition_count: Mapped[int] = mapped_column(Integer)

class SparkTimeSummary(Base):
    __tablename__ = "spark_time_summary"
    time_bucket: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    telemetry_record_count: Mapped[int] = mapped_column(Integer)
    safety_condition_count: Mapped[int] = mapped_column(Integer)

class SparkSoftwareSummary(Base):
    __tablename__ = "spark_software_summary"
    software_version: Mapped[str] = mapped_column(String(30), primary_key=True)
    telemetry_count: Mapped[int] = mapped_column(Integer)
    safety_condition_count: Mapped[int] = mapped_column(Integer)
