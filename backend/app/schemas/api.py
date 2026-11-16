from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class FarsCrashOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    year: int
    state_name: str | None
    county_name: str | None
    city_name: str | None
    crash_date: date | None
    hour: int | None
    latitude: float | None
    longitude: float | None
    fatalities: int
    pedestrians: int | None
    vehicles: int | None
    weather: str | None
    light_condition: str | None
    junction: str | None
    road_class: str | None
    road_name: str | None
    first_harmful_event: str | None
    speeding_involved: bool
    drinking_driver_involved: bool
    max_speed_limit_mph: int | None
    flags: list[str] = []


class NycCrashOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    collision_id: str
    crash_datetime: datetime
    borough: str | None
    latitude: float | None
    longitude: float | None
    on_street: str | None
    cross_street: str | None
    off_street: str | None
    persons_injured: int
    persons_killed: int
    pedestrians_injured: int
    pedestrians_killed: int
    cyclists_injured: int
    cyclists_killed: int
    vehicle_types: list[str]
    contributing_factors: list[str] = []
    flags: list[str] = []
