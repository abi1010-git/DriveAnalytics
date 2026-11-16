import pytest

from app.services.rule_engine import RuleSet, evaluate_record, load_rules


def rules(*conditions, match="all", enabled=True, source="fars"):
    return RuleSet.model_validate({"rules": [{"id": "r", "name": "R", "description": "D", "source": source, "category": "behavior",
                                              "enabled": enabled, "match": match, "conditions": list(conditions)}]}).rules


def cond(field, operator, value):
    return {"field": field, "operator": operator, "value": value}


@pytest.mark.parametrize("op,value,observed,expected", [
    ("gt", 5, 6, True), ("gt", 5, 5, False), ("gte", 5, 5, True), ("lt", 5, 4, True), ("lte", 5, 5, True),
    ("eq", 2, 2, True), ("neq", 2, 3, True), ("in", [0, 1, 2], 1, True), ("in", [0, 1, 2], 7, False),
])
def test_operators(op, value, observed, expected):
    assert bool(evaluate_record({"hour": observed}, rules(cond("hour", op, value)))) is expected


def test_contains_any_on_list_fields():
    rule = rules(cond("contributing_factors", "contains_any", ["Unsafe Speed"]), source="nyc")
    assert evaluate_record({"contributing_factors": ["Unspecified", "Unsafe Speed"]}, rule)
    assert not evaluate_record({"contributing_factors": ["Unspecified"]}, rule)


def test_unknown_values_never_match():
    assert evaluate_record({"hour": None}, rules(cond("hour", "lt", 5))) == []
    assert evaluate_record({}, rules(cond("hour", "neq", 5))) == []


def test_all_any_disabled_and_evidence():
    both = [cond("pedestrians", "gt", 0), cond("hour", "in", [0, 1])]
    assert evaluate_record({"pedestrians": 1, "hour": 9}, rules(*both)) == []
    hit = evaluate_record({"pedestrians": 1, "hour": 9}, rules(*both, match="any"))[0]
    assert hit["flag_id"] == "r" and hit["evidence"] == [{"field": "pedestrians", "operator": "gt", "threshold": 0, "observed": 1}]
    assert evaluate_record({"pedestrians": 1}, rules(cond("pedestrians", "gt", 0), enabled=False)) == []


@pytest.mark.parametrize("bad", [
    {"conditions": [cond("speed_mph", "gt", 1)]},  # field the source does not have
    {"conditions": [cond("hour", "eval", 1)]},  # operator outside the whitelist
    {"conditions": [cond("hour", "in", 3)]},  # list operator without a list
    {"conditions": [cond("contributing_factors", "contains_any", ["x"])]},  # NYC field on a FARS rule
    {"category": "vibes"},
    {"source": "chicago"},
    {"severity": "HIGH"},  # unknown keys are rejected, not ignored
])
def test_invalid_rules_rejected(bad):
    rule = {"id": "r", "name": "R", "description": "D", "source": "fars", "category": "behavior", "conditions": [cond("hour", "gt", 1)]}
    rule.update(bad)
    with pytest.raises(ValueError):
        RuleSet.model_validate({"rules": [rule]})


def test_duplicate_ids_rejected():
    rule = {"id": "r", "name": "R", "description": "D", "source": "fars", "category": "behavior", "conditions": [cond("hour", "gt", 1)]}
    with pytest.raises(ValueError):
        RuleSet.model_validate({"rules": [rule, rule]})


def test_shipped_config_is_valid():
    shipped = load_rules()
    assert shipped.for_source("fars") and shipped.for_source("nyc")
