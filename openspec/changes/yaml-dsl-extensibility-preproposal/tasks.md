## 1. Review & Split (pre-proposal)

- [ ] 1.1 Review `proposal.md` for full-scope acceptance (BUNDLE + ANALYZE + direct config)
- [ ] 1.2 Confirm YAML shape and naming (`bundles/analyze/compute/components/outputs/aggregates/transform`)
- [ ] 1.3 Confirm conflict policy defaults and required diagnostics
- [ ] 1.4 Split implementation into multiple OpenSpec changes (schema/host/analyze/outputs/aggregates/cli/docs) with clear dependency order

## 2. Schema & Loader Scaffolding

- [ ] 2.1 Add `extensions` to canonical schema (`DemandConfig`) with minimal shape for bundles/analyze/direct config
- [ ] 2.1.1 Add `extensions.api` + `extensions.conflicts` minimal schema shape
- [ ] 2.2 Ensure `extensions` supports `additionalProperties` (extension-defined keys/options do not break schema-only validation)
- [ ] 2.3 Update parser/loaders to preserve/parse `extensions` payload as needed (without breaking existing YAML)
- [ ] 2.3.1 Refactor loader pipeline to allow: build ExtensionHost → raw transformers → validator → parse
- [ ] 2.4 Add/adjust tests to guard schema drift + `extensions` acceptance
- [ ] 2.5 Update frontend schema mirrors + drift gates (if editor/viz checks are in default QA)

## 3. Extension Host Core (Registries + Bundles)

- [ ] 3.1 Define runtime contracts (`ExtensionBundle`, contexts, error wrappers, registry interfaces) under `src/scalim/`
- [ ] 3.1.1 Define `ExtensionHost` + `ExtensionHost.summary` (single SSOT for validator/parser/compiler/executor/CLI)
- [ ] 3.2 Implement `ref + config` generic instantiation/call strategy (supports functions/classes/factories)
- [ ] 3.3 Parse `extensions` config and resolve refs via `SecurePythonReferenceResolver` (including relative refs)
- [ ] 3.4 Merge contributions deterministically (direct config + bundles) with configurable conflict policies
- [ ] 3.5 Surface diagnostics: include yaml_path/ref/stage and final extensions summary for to-diff

## 4. ANALYZE Pipeline (extensions.analyze)

- [ ] 4.1 Define analyzer contract + result shape (issues + optional meta)
- [ ] 4.2 Decide analyzer execution stages (raw and/or compiled) and wire into compiler/validator/CLI
- [ ] 4.3 Add regression tests: analyzer warnings/errors appear in outputs when enabled

## 5. Compute Functions Extension

- [ ] 5.1 Extend compute engine creation to accept extra functions (name → callable)
- [ ] 5.2 Fix compute dependency inference to ignore function names (Call.func) and only collect field names
- [ ] 5.3 Wire validator + YAML outputs parser + runtime output composition to use the same extended compute engine
- [ ] 5.4 Add regression tests: derived `compute` + outputs `where` accept extension functions without false “unknown field fn_name”

## 6. YAML Components Injection

- [ ] 6.1 Define YAML syntax for declaring components (ref + config) and resolve/instantiate at compile time
- [ ] 6.2 Assemble resolved components together with existing `observability.*` observers
- [ ] 6.3 Reuse `split_components` for strict type checking and early failure
- [ ] 6.4 Add regression tests: valid observer/hook works; invalid component fails with actionable TypeError

## 7. Output Format Registry (single output + composed outputs)

- [ ] 7.1 Define `format_id → factory` registry API usable by both single output and composed outputs
- [ ] 7.2 Route `run_ir` single-output sink creation through registry (keep csv/excel built-ins)
- [ ] 7.3 Route composed outputs sink creation through registry (keep csv/excel built-ins)
- [ ] 7.4 Update YAML schema/models: allow `outputs[*].container.type` to be custom format id + allow `container.options`
- [ ] 7.4.1 Decide and implement `container.options` runtime contract (pass to factory; keep built-ins ignoring it)
- [ ] 7.4.2 Add container handle support for shared resources (workbook-style), keyed by deterministic container_key
- [ ] 7.5 Add tests: custom format factory produces a sink and is used end-to-end (single + composed)

## 8. Custom Aggregates (outputs.*.aggregate)

- [ ] 8.1 Update YAML schema/models to allow aggregate `kind/ref` + `options/config` (keep built-in group_by)
- [ ] 8.2 Define aggregate factory return contract (derived spec + output_field_ids) and compile via resolver/registry
- [ ] 8.2.1 Ensure custom aggregate compilation happens early enough to inject `required_fields()` before field slicing
- [ ] 8.3 Enforce parallel_mode validation for custom derived specs (fail-fast)
- [ ] 8.4 Add tests: custom aggregator receives rows, accumulates, and emits derived output rows

## 9. Transformers (raw/config/ir/request)

- [ ] 9.1 Define transformer stage APIs and deterministic ordering
- [ ] 9.2 Implement raw transformer hook point before core validator
- [ ] 9.3 Implement config/ir/request transformers in compiler pipeline
- [ ] 9.4 Add tests: raw transformer affects validation + compiled behavior consistently

## 10. CLI, Docs, Examples, QA Gates

- [ ] 10.1 Add CLI flags to resolve extensions (allowlist, trusted shortcut) and integrate analyzer output
- [ ] 10.1.1 Add `--allow-module/--allow-function` flags and `--trusted` wildcard shortcut with warning
- [ ] 10.1.2 Default validate prints actionable hint when extension syntax is present but not resolved
- [ ] 10.2 Add “extensions quickstart” doc + full examples (BUNDLE + ANALYZE + direct config)
- [ ] 10.3 Update canonical demo YAML if authoring surface changes
- [ ] 10.4 Run `just gen-docs` and ensure injected blocks/schema mirrors are consistent
- [ ] 10.5 Run `just qa` and `just openspec-check`
