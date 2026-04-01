## 1. P0 Drift Stopgap (v1)

- [ ] 1.1 Add drift gate: compare workflow schema vs runtime allowed keys for `workflow.resources` (fail CI on mismatch)
- [ ] 1.2 Remove/hide `$import` from `src/scalim/dsl/by_yaml/schema/workflow.gen.json` resources nodes (SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**`; regen via `scripts/gen-yaml-dsl-schema.py`)
- [ ] 1.3 Fix schema numeric typing holes: add `type:number|integer` for all fields using numeric constraints (regen + update drift tests)
- [ ] 1.4 Align workflow validation error messages: `$import` under workflow resources MUST fail-fast with actionable migration hint

## 2. vNext Schema Artifacts (Parallel to v1)

- [ ] 2.1 Define vNext authoring models/metadata in `src/scalim/dsl/by_yaml/schema_dsl/**` (authoring-core-only; no runtime control-plane keys)
- [ ] 2.2 Generate vNext schema artifacts: `src/scalim/dsl/by_yaml/schema/demand.vnext.gen.json` and `src/scalim/dsl/by_yaml/schema/workflow.vnext.gen.json` (generated; no hand edits)
- [ ] 2.3 Add drift tests for vNext schemas (patterned after `tests/test_yaml_schema_generation.py`)
- [ ] 2.4 Extend `scalim-cli yaml-dsl schema path/validate` to support selecting v1 vs vNext schema (acceptance: `just qa`)

## 3. vNext Validators / Parsers

- [ ] 3.1 Implement vNext demand validator: reject runtime control-plane keys with actionable hints (acceptance: new targeted tests + CLI validate)
- [ ] 3.2 Implement vNext workflow validator: keep `workflow.options` surface small; reject diagnostics/staging options (acceptance: new targeted tests)
- [ ] 3.3 Ensure vNext errors preserve precise YAML logical path + location envelopes (no “(root)” ambiguity)

## 4. Runtime Control-Plane Migration

- [ ] 4.1 Move `observability.*` knobs out of YAML: provide Python/CLI equivalents (SSOT: `RunOptions.components` / `RunOverrides.viz_config`; acceptance: docs+examples updated)
- [ ] 4.2 Move `guardrails.*` out of YAML: standardize on `RunOptions.guardrails` (acceptance: vNext schema rejects YAML guardrails)
- [ ] 4.3 Move `retry.*` out of YAML: standardize on `RunOptions.loader_retry` (acceptance: remove CLI-only hidden rules like enabled+should_retry)
- [ ] 4.4 Add typed overrides for vNext output extras (meta/audit) per spec (acceptance: unit tests + one end-to-end notebook example)

## 5. Write Policy SSOT & De-duplication

- [ ] 5.1 Decide & codify SSOT: `resources.books.*.write_defaults` is the only defaults surface; `outputs[*].write` becomes minimal override-only
- [ ] 5.2 Update demand/workflow schemas + runtime to match the SSOT (acceptance: regression tests for precedence and conflict behavior)
- [ ] 5.3 Update typed overrides to match the SSOT (avoid “same knob in 3 places”)

## 6. Imports/$import Restriction & Migration Tooling

- [ ] 6.1 Implement vNext `$import` restriction rules (forbid under resources/policy/diagnostics areas; forbid in workflow)
- [ ] 6.2 Add `scalim-cli yaml-dsl upgrade --to vnext` (or equivalent) to auto-migrate common patterns (acceptance: golden fixtures)
- [ ] 6.3 Ensure `render effective` output can produce import-free effective YAML for debugging/migration (acceptance: deterministic output + CI fixture)

## 7. Docs / Examples / Skills Alignment

- [ ] 7.1 Update docs to vNext guidance (SSOT: non-`.gen.` docs; injected blocks via `just gen-docs`; acceptance: `just gen-docs` + `just qa`)
- [ ] 7.2 Update notebooks YAML fixtures to use vNext (or mark as v1 explicitly with schema/modeline)
- [ ] 7.3 Replace internal imports used by tooling packages with stable helpers (extend `scalim.dsl.by_yaml.tools` as needed)

## 8. Deprecation & Removal

- [ ] 8.1 Add v1 deprecation warnings for keys removed from vNext (emit once per run; include migration hint)
- [ ] 8.2 Define removal timeline and enforce via CI (fail on new usage in repo examples/fixtures)

