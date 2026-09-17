from datetime import datetime
from pydantic import BaseModel, ConfigDict

class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; vehicle_name: str; software_version: str; status: str

class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; vehicle_id: int; timestamp: datetime; speed_mph: float; acceleration_mps2: float
    steering_angle: float; brake_pressure: float; battery_percent: float; sensor_status: str; route_id: str

class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; vehicle_id: int; timestamp: datetime; event_type: str; severity: str
    description: str; software_version: str; route_id: str

class EventDetail(EventOut):
    vehicle: VehicleOut
    nearby_telemetry: list[TelemetryOut]

class SparkVehicleSummaryOut(BaseModel):
    vehicle_id: int; telemetry_record_count: int; average_speed: float; max_speed: float
    hard_braking_count: int; rapid_acceleration_count: int; sensor_failure_count: int

class SparkRouteSummaryOut(BaseModel):
    route_id: str; telemetry_record_count: int; average_speed: float; safety_condition_count: int
