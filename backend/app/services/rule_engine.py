"""YAML-configured risk-factor flags for crash records.

Each rule names a data source, a category and one or more conditions over whitelisted
fields. Rules are data, never code: YAML is read with safe_load, and only the
operators below can be used.
"""
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SOURCE_FIELDS = {
    "fars": {
        "hour", "fatalities", "persons", "pedestrians", "vehicles", "weather_code", "light_code",
        "junction_code", "rural_urban", "road_class", "speeding_involved", "drinking_driver_involved",
        "max_speed_limit_mph", "first_harmful_event",
    },
    "nyc": {
        "hour", "borough", "persons_injured", "persons_killed", "pedestrians_injured", "pedestrians_killed",
        "cyclists_injured", "cyclists_killed", "motorists_injured", "motorists_killed",
        "contributing_factors", "vehicle_types",
    },
}
OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq", "in", "contains_any"}
CATEGORIES = {"behavior", "environment", "road", "vulnerable_road_user", "outcome"}
RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "risk_flags.yaml"


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    operator: str
    value: Any

    @field_validator("operator")
    @classmethod
    def supported_operator(cls, value):
        if value not in OPERATORS:
            raise ValueError(f"unsupported operator: {value}")
        return value

    @model_validator(mode="after")
    def list_value_for_list_operators(self):
        if self.operator in {"in", "contains_any"} and not isinstance(self.value, list):
            raise ValueError(f"operator {self.operator} needs a list value")
        return self


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: Literal["fars", "nyc"]
    category: str
    enabled: bool = True
    match: Literal["all", "any"] = "all"
    conditions: list[Condition] = Field(min_length=1)

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value not in CATEGORIES:
            raise ValueError(f"unsupported category: {value}")
        return value

    @model_validator(mode="after")
    def fields_exist_for_source(self):
        for condition in self.conditions:
            if condition.field not in SOURCE_FIELDS[self.source]:
                raise ValueError(f"unsupported field for {self.source}: {condition.field}")
        return self


class RuleSet(BaseModel):
    rules: list[Rule]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule IDs must be unique")
        return self

    def for_source(self, source: str) -> list[Rule]:
        return [rule for rule in self.rules if rule.enabled and rule.source == source]


def load_rules(path: str | Path = RULES_PATH) -> RuleSet:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        return RuleSet.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
        raise ValueError(f"invalid risk flag configuration: {exc}") from exc


def _matches(condition: Condition, record: dict[str, Any]) -> bool:
    observed, target = record.get(condition.field), condition.value
    if observed is None:
        return False  # unknown never counts as a match
    op = condition.operator
    if op == "in":
        return observed in target
    if op == "contains_any":
        return any(item in target for item in observed)
    if op == "eq":
        return observed == target
    if op == "neq":
        return observed != target
    try:
        if op == "gt":
            return observed > target
        if op == "gte":
            return observed >= target
        if op == "lt":
            return observed < target
        return observed <= target
    except TypeError:
        return False


def evaluate_record(record: dict[str, Any], rules: list[Rule]) -> list[dict[str, Any]]:
    """Return the rules that match one record, with the observed values that made them match."""
    triggered = []
    for rule in rules:
        if not rule.enabled:
            continue
        matches = [_matches(condition, record) for condition in rule.conditions]
        if all(matches) if rule.match == "all" else any(matches):
            evidence = [
                {"field": c.field, "operator": c.operator, "threshold": c.value, "observed": record.get(c.field)}
                for c, matched in zip(rule.conditions, matches) if matched
            ]
            triggered.append({"flag_id": rule.id, "name": rule.name, "category": rule.category, "evidence": evidence})
    return triggered


def flag_ids(record: dict[str, Any], rules: list[Rule]) -> list[str]:
    return [item["flag_id"] for item in evaluate_record(record, rules)]
