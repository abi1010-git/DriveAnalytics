# SafeDrive Safety Rule Engine

## Purpose

The rule engine lets engineering users adjust illustrative telemetry checks in YAML instead of changing evaluator code. It evaluates only synthetic SafeDrive telemetry and is not a certified safety system.

## Architecture

```text
Synthetic telemetry -> Safety Rule Engine <- YAML rules
                              |
                              v
                    Triggered evaluations -> PostgreSQL -> FastAPI -> React
```

## Rule Format

Rules contain a unique `id`, name, description, enabled flag, severity, match mode, and one or more conditions:

```yaml
rules:
  - id: hard_braking
    name: Hard Braking
    description: Illustrative negative-acceleration check.
    enabled: true
    severity: HIGH
    conditions:
      - field: acceleration_mps2
        operator: lt
        value: -4.5
```

Supported fields are whitelisted telemetry fields and supported operators are `gt`, `gte`, `lt`, `lte`, `eq`, and `neq`. `match: all` is the default; `match: any` is also supported. YAML is parsed with `safe_load`; no expressions or Python code are executed.

## Evaluation and Evidence

`backend/scripts/evaluate_safety_rules.py` loads validated rules, streams telemetry records, evaluates enabled rules, and persists only triggered evaluations. Each evaluation stores observed values, operators, and thresholds as structured JSON so an engineer can explain why it triggered.

## Adding a Rule

Add a validated rule to `backend/config/safety_rules.yaml`, then run:

```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg2://postgres@127.0.0.1:5432/safedrive"
python scripts/evaluate_safety_rules.py --max-records 100000
```

Inspect rules at `GET /api/safety/rules` and evaluations at `GET /api/safety/evaluations`.

## Testing

The rule-engine tests cover all six operators, boundaries, all/any matching, disabled rules, malformed configurations, unsupported fields/operators, evidence, and multiple triggers.

## Limitations

Rules and thresholds are illustrative, all telemetry is synthetic, and SafeDrive is an educational portfolio project. This engine does not represent actual autonomous-vehicle, regulatory, industry, or Zoox safety requirements and is not a certified safety system.
