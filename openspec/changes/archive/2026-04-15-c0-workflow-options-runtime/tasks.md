## 1. Public API: `workflow_runtime_options` typed surface

- [x] 1.1 Define `WorkflowRuntimeOptions` (and orthogonal sub-options/presets) on a stable import path, Python 3.6 compatible
- [x] 1.2 Update `run_workflow(...)` entrypoints to accept `workflow_runtime_options=...` and remove/replace `workflow_resources_wait` / `workflow_output_staging` kwargs

## 2. YAML runtime policy boundary: forbid `workflow.options`

- [x] 2.1 Update workflow YAML parser to fail-fast on `workflow.options` (and its subfields) with an actionable migration hint to runtime entrypoints (`workflow_runtime_options`)
- [x] 2.2 Update workflow YAML schema SSOT to remove `workflow.options` and regenerate `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` via `just gen-yaml-dsl-schema` (do not hand-edit `*.gen.*`)

## 3. Compile/IR wiring: runtime options -> `WorkflowOptionsIr`

- [x] 3.1 Update workflow compile to build `WorkflowOptionsIr` from `workflow_runtime_options` (execution/cache_pool/resources_wait/output_staging) instead of YAML options
- [x] 3.2 Remove `ctx` guardrail options from workflow config/IR models (keep `$ctx` semantics but delete size-limit knobs)

## 4. Remove `$ctx` size guardrails (behavior + surface)

- [x] 4.1 Remove `workflow.options.ctx` config surface end-to-end (models/parser/docs/migration errors)
- [x] 4.2 Remove runtime size-limit enforcement in `WorkflowCtxStore.publish()` (no max_value_bytes/max_bytes fail-fast)

## 5. Cache pool: runtime-only preset, minimal knobs

- [x] 5.1 Implement runtime-only cache_pool presets (default disabled; `preload_forever` shared preset with `max_entries` default 16; other knobs fixed)
- [x] 5.2 Ensure legacy YAML cache_pool config is rejected and migration hint points to runtime preset

## 6. Tests + generated references (drift-safe)

- [x] 6.1 Add/adjust tests for: YAML rejection of `workflow.options`; `workflow_runtime_options` options applied; ctx store no longer rejects large payloads
- [x] 6.2 Regenerate docs/skills/schema and pass gates: `just gen-yaml-dsl-schema`, `just gen-agent-skill`, `just gen-docs`, then `just qa` (and `just openspec-check` before sharing)
