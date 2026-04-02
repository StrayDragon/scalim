## 1. Public API surface

- [x] 1.1 Add `run_patches_by_id` parameter to `scalim.dsl.by_yaml.run_workflow(...)` and stable entrypoint import path (`scalim.dsl.by_yaml.workflow_entrypoints.run_workflow`)
- [x] 1.2 Introduce typed per-run patch models (Python 3.6 compatible) and expose them via a stable import path (e.g. `scalim.dsl.by_yaml.workflow_types`)
- [x] 1.3 Reject legacy/untyped patch values (e.g. `dict` patch payloads) with actionable error messages

## 2. Core behavior (merge + precedence)

- [x] 2.1 Validate `run_patches_by_id` keys against `workflow.runs[*].id` and fail-fast on unknown ids (include known ids in error)
- [x] 2.2 Implement per-run `batch_size` inherit/disable/override semantics and verify precedence over global `run_workflow(batch_size=...)`
- [x] 2.3 Implement `components` patch semantics (replace / extend / disable) and document thread-safety expectations for workflow concurrency
- [x] 2.4 Implement per-run `RunOverrides` patch semantics (inherit / disable / replace), ensuring workflow `resources` overlay still applies and per-run resources win on conflicts
- [x] 2.5 Enforce the security boundary: per-run patches MUST NOT be able to override `allowed_modules/allowed_functions/resolver_trusted_mode` (typed surface + runtime validation where applicable)

## 3. Tests

- [x] 3.1 Add workflow tests: two runs with different per-run `batch_size` plus a global default
- [x] 3.2 Add workflow tests: unknown run id in `run_patches_by_id` fails fast with diagnostics
- [x] 3.3 Add workflow tests: `components` replace vs extend semantics (including disable via empty list)
- [x] 3.4 Add workflow tests: per-run overrides precedence over workflow resources overlay (resources deep-merge) and over global overrides

## 4. Docs / DX

- [x] 4.1 Update `docs/doc/yaml-dsl/workflow.md` to document `run_patches_by_id` usage with 2-3 minimal examples (batch_size only; batch_size + components; disabling a global knob for one run)
- [x] 4.2 Add/adjust error message guidance in docs for common misconfigs (unknown ids; patch value type errors; forbidden security overrides)

## 5. Verification

- [x] 5.1 Run `just openspec-check` to validate/sanitize OpenSpec artifacts
- [x] 5.2 Run a focused pytest subset covering workflow entrypoints and runtime compilation (avoid unrelated test churn)
