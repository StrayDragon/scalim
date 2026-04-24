# scalim-cli

Standalone command-line utilities for `scalim` (dev/tooling only).

Install:

```bash
uv tool install scalim-cli

# Run once without installing:
uvx scalim-cli --help
```

Usage:

```bash
scalim-cli --help
scalim-cli yaml-dsl --help
```

## YAML DSL viz export (static)

`scalim-cli yaml-dsl viz compile` exports **static** viz artifacts for `frontend/scalim-viz` replay/inspection.

```bash
# demand -> writes <dir>/viz_snapshot.json + <dir>/viz_schedule_plan.json
scalim-cli yaml-dsl viz compile --type demand path/to/report.demand.yaml --output-dir .tmp/viz_report

# workflow -> writes a scalim-viz bundle under <dir>/scalim-viz/
scalim-cli yaml-dsl viz compile --type workflow path/to/report.workflow.yaml --output-dir .tmp/viz_bundle
```

## YAML DSL validation layers

`scalim-cli yaml-dsl` exposes two validation entrypoints with different responsibilities:

- `scalim-cli yaml-dsl validate <file.yaml>`: runtime-parity validation (semantic + unknown-fields diagnostics).
  - Does **not** run JSON Schema validation.
  - Does **not** emit “jsonschema 不可用 / 已跳过 schema 校验” warnings.
  - Suitable for “will this config be accepted by runtime parse/compile/run?” checks.

- `scalim-cli yaml-dsl schema validate <file.yaml>`: schema-only validation (structure/type) using JSON Schema.
  - Requires the `jsonschema` dependency (Draft7).
  - Fails fast with actionable error output when `jsonschema` is unavailable.
  - Suitable for fast authoring feedback and editor/LSP parity checks.
