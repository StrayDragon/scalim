## 1. Schema SSOT & Authoring Surface

- [ ] 1.1 Add `default`/`default_by` to `SourceFieldConfig` SSOT (`src/scalim/dsl/yaml_dsl/schema_dsl/models/field.py`) (DoD: schema-only validate accepts keys; strict validator not yet required)
- [ ] 1.2 Add `ensure_keys` model under `OutputTargetConfig` SSOT (`src/scalim/dsl/yaml_dsl/schema_dsl/models/outputs.py`) (DoD: schema exposes `outputs[*].ensure_keys`)
- [ ] 1.3 Update schema docs/hover text for new fields (SSOT: `src/scalim/dsl/yaml_dsl/schema_dsl/**`) (DoD: hover 文案说明边界：miss-only、aggregate-only、on optional)

## 2. Strict Validation & Parsing

- [ ] 2.1 Parse `default/default_by` in field parser (`src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/fields.py`) (DoD: `SourceFieldConfig` 实例可读到新字段)
- [ ] 2.2 Add strict validator rules for field defaults (`src/scalim/dsl/yaml_dsl/_internal/config_parsing/validators/**`) (DoD: 互斥 + ref-only fail-fast)
- [ ] 2.3 Add strict validator rules for `outputs[*].ensure_keys` (DoD: aggregate-only; `from` exists; `on` optional but if present equals group_by; defaults keys in output fields)
- [ ] 2.4 Add validator tests for: mutual exclusivity, non-ref rejection, ensure_keys invalid ref, ensure_keys on mismatch (DoD: tests fail before fix and pass after)

## 3. Planning-Time Constraints (Default By Dependencies)

- [ ] 3.1 Define rule: `default_by` deps MUST be pre-ref available (main_source non-ref + pre-ref derived) (DoD: rule written in code comments + error message includes blocking chain)
- [ ] 3.2 Implement planner validation for `default_by` deps (suggest: `src/scalim/planning/builder.py`) (DoD: invalid YAML fails before run with actionable error)
- [ ] 3.3 Add tests that cover: allowed deps; rejected deps referencing ref field / post-ref derived (DoD: stable error snapshot)

## 4. IR & Runtime Linking (Field Defaults)

- [ ] 4.1 Extend `FieldIr` to carry default spec (literal + optional call_by spec + deps) (`src/scalim/spec/ir/_fields.py`) (DoD: IR roundtrip compiles)
- [ ] 4.2 Populate default spec in YAML→IR conversion (`src/scalim/dsl/yaml_dsl/runtime/_internal/conversion_sources.py`) (DoD: config→IR includes defaults)
- [ ] 4.3 Extend `RuntimeBindings` to register per-field default calculators (`src/scalim/execution/runtime_bindings.py`) (DoD: default_by calculator lookup works)
- [ ] 4.4 Resolve `default_by` callables in runtime linking (`src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py`) (DoD: allowlist/builtin 语义与 call_by 一致，签名预检查可复用)
- [ ] 4.5 Apply defaults on relation miss in LoadRef writeback (`src/scalim/execution/executor/operators/load_ref/flow.py`) (DoD: miss 时写回 default 值且仍执行 value_cast)
- [ ] 4.6 Add execution tests for: hit vs miss, null-fk miss, multi-step miss, default_by uses ctx/fields (DoD: tests cover semantics + guardrails mode)

## 5. `ensure_keys` for Derived Outputs

- [ ] 5.1 Compile `outputs[*].ensure_keys` from YAML (`src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py`) (DoD: derived target spec carries ensure_keys config)
- [ ] 5.2 Implement `EnsureKeysAggregator` wrapper (suggest: `src/scalim/execution/derived_outputs.py` or `src/scalim/execution/output_composition.py`) (DoD: missing groups are filled with identity/defaults)
- [ ] 5.3 Implement key provider for dimension source mapping keys (DoD: load once per run; respects normalize; handles composite keys)
- [ ] 5.4 Add ensure_keys diagnostics via `aggregator.diagnostics()` meta + audit_events (DoD: meta has filled_count/ratio; high ratio emits audit event)
- [ ] 5.5 Add tests for ensure_keys: single key, composite key, rank_fields present ordering rule, stable determinism (DoD: tests pass on repeated runs)

## 6. Generated Artifacts & Docs Governance

- [ ] 6.1 Regenerate YAML schema via `just gen-yaml-dsl-schema` (SSOT: `src/scalim/dsl/yaml_dsl/schema_dsl/**`; generated: `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`) (DoD: drift tests pass; do not hand-edit `*.gen.*`)
- [ ] 6.2 Refresh docs injected blocks via `just gen-docs` if any docs touch (DoD: no manual edits inside `BEGIN/END AUTOGEN` blocks)
- [ ] 6.3 Add/update a non-generated example demand YAML demonstrating both features (DoD: reviewer can copy-paste to reproduce)

## 7. Quality Gates

- [ ] 7.1 Run `just qa` (fix only regressions introduced by this change) (DoD: lint/tests pass)
- [ ] 7.2 Run `just openspec-check` (DoD: sanitize + openspec validate clean)
