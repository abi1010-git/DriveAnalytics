# Risk-factor flags

## What they are

A risk flag is a named fact about a crash, such as "speeding involved", "dark, no street lighting" or "pedestrian injured or killed". Flags are defined in `backend/config/risk_flags.yaml` and attached to crashes when they are loaded. Flags make questions like "how many fatal crashes in Texas involved speeding on unlit roads?" a simple join, and let anyone read exactly how each flag is defined.

A flag records what police reported. It does not establish what caused the crash.

## Rule format

```yaml
rules:
  - id: fars_dark_unlit
    name: Dark, no street lighting
    description: Light condition coded as "Dark - Not Lighted" (LGT_COND 2).
    source: fars            # fars or nyc: which dataset the rule reads
    category: environment   # behavior | environment | road | vulnerable_road_user | outcome
    match: all              # all (default) or any
    conditions:
      - {field: light_code, operator: eq, value: 2}
```

- **Fields** are whitelisted per source. A FARS rule can't name an NYC field, and the reverse is also rejected. The lists are `SOURCE_FIELDS` in `backend/app/services/rule_engine.py`.
- **Operators:** `gt`, `gte`, `lt`, `lte`, `eq`, `neq`, `in` (value is in a list) and `contains_any` (a list field such as `contributing_factors` shares an item with the given list).
- **Unknown values never match.** If a crash's hour is unknown, it is never flagged as "late night".
- **Validation:** YAML is read with `safe_load` and checked with Pydantic. Unknown keys, fields, operators, categories and duplicate IDs are all rejected. No expression or code in the file is ever executed.

## Changing a flag

1. Edit `backend/config/risk_flags.yaml`.
2. Re-run the loaders. They read the local raw cache, so nothing is downloaded again:

   ```powershell
   cd backend
   python -m pipeline fars --years 2020-2024
   python -m pipeline nyc --file data/raw/nyc/crashes_full.jsonl.gz
   ```

3. `GET /api/risk-flags` lists every flag with how many crashes it matched.

## History

This engine started as the "safety rule engine" for the earlier, synthetic version of this project, which flagged telemetry readings such as hard braking. The evaluator and validation design stayed. The fields, operators (`in` and `contains_any` were added) and rules were rewritten for real crash records.
