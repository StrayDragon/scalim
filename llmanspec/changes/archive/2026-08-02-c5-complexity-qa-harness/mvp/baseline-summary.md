# ENTRY baseline summary (c5-complexity-qa-harness)

Captured via `scripts/check-complexity.py --write-baseline`.

| Metric | Baseline max | Headroom | Pinned threshold |
|--------|-------------:|---------:|-----------------:|
| cognitive (Sonar) | 75 | +5 | **MAX_COGNITIVE = 80** |
| cyclomatic (McCabe) | 39 | +5 | **MAX_CYCLOMATIC = 44** |

Hottest function (both metrics): `compile_output_composition_from_yaml` in
`src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py`.

Machine-readable: [`baseline-entry.json`](baseline-entry.json).
