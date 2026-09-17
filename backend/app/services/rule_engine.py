"""Small, deterministic YAML-driven rule evaluator; never executes YAML as code."""
from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SUPPORTED_FIELDS = {"vehicle_id", "speed_mph", "acceleration_mps2", "steering_angle", "brake_pressure", "battery_percent", "sensor_status", "route_id", "software_version"}
SUPPORTED_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

class Condition(BaseModel):
    field: str
    operator: str
    value: Any
    @field_validator("field")
    @classmethod
    def supported_field(cls, value):
        if value not in SUPPORTED_FIELDS: raise ValueError(f"unsupported rule field: {value}")
        return value
    @field_validator("operator")
    @classmethod
    def supported_operator(cls, value):
        if value not in SUPPORTED_OPERATORS: raise ValueError(f"unsupported rule operator: {value}")
        return value

class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    enabled: bool = True
    severity: str
    conditions: list[Condition] = Field(min_length=1)
    match: Literal["all", "any"] = "all"
    @field_validator("severity")
    @classmethod
    def valid_severity(cls, value):
        value = value.upper()
        if value not in SEVERITIES: raise ValueError(f"unsupported severity: {value}")
        return value

class RuleSet(BaseModel):
    rules: list[Rule]
    @model_validator(mode="after")
    def unique_ids(self):
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)): raise ValueError("rule IDs must be unique")
        return self

def load_rules(path: str | Path) -> RuleSet:
    try:
        with Path(path).open(encoding="utf-8") as handle: raw = yaml.safe_load(handle)
        return RuleSet.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
        raise ValueError(f"invalid safety rule configuration: {exc}") from exc

def _matches(condition: Condition, telemetry: dict[str, Any]) -> bool:
    observed = telemetry.get(condition.field); target = condition.value
    if observed is None: return False
    if condition.operator == "gt": return observed > target
    if condition.operator == "gte": return observed >= target
    if condition.operator == "lt": return observed < target
    if condition.operator == "lte": return observed <= target
    if condition.operator == "eq": return observed == target
    return observed != target

def evaluate_record(telemetry: dict[str, Any], rules: RuleSet) -> list[dict[str, Any]]:
    triggered = []
    for rule in rules.rules:
        if not rule.enabled: continue
        matches = [_matches(condition, telemetry) for condition in rule.conditions]
        if (all(matches) if rule.match == "all" else any(matches)):
            evidence = [{"field": condition.field, "operator": condition.operator, "threshold": condition.value, "observed": telemetry.get(condition.field)} for condition, matched in zip(rule.conditions, matches) if matched]
            triggered.append({"rule_id": rule.id, "rule_name": rule.name, "severity": rule.severity, "triggered": True, "evidence": evidence})
    return triggered
