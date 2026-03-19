## 1. Public API & Contracts

- [ ] 1.1 Extend `RunOptions` with `template_vars` injection
- [ ] 1.2 Add `template_vars` to by_yaml `run/compile` entrypoints and thread to YAML load stage
- [ ] 1.3 Add `template_vars` to workflow `run_workflow` entrypoint and apply to workflow YAML loading

## 2. LiteJinja2 strict-undefined

- [ ] 2.1 Implement strict-undefined mode in `src/scalim/vendor/litejinja2/` (default behavior unchanged)
- [ ] 2.2 Make `default` filter treat undefined values as missing under strict mode
- [ ] 2.3 Add unit tests for strict-undefined + `default(...)` fallback behavior

## 3. YAML Text Precompile Pipeline

- [ ] 3.1 Add a reusable helper to render YAML text via LiteJinja2 with caching + context labels
- [ ] 3.2 Integrate precompile into demand YAML loader (`YamlDemandLoader`) for path-based loads
- [ ] 3.3 Thread `template_vars` into `imports/$import` fragment loading so fragments are also precompiled
- [ ] 3.4 Integrate precompile into workflow YAML loader (`load_workflow_config`) before YAML parse

## 4. Error Semantics & Diagnostics

- [ ] 4.1 Fail-fast on missing template vars with message including missing var name + YAML file context
- [ ] 4.2 Ensure import-fragment failures include import trace (at least fragment file path)
- [ ] 4.3 Ensure templating is opt-in: when `template_vars` is not provided, no template rendering is attempted

## 5. Tests & Quality Gates

- [ ] 5.1 Add integration tests: demand YAML supports `path: {{ output_path }}` (unquoted) via `template_vars`
- [ ] 5.2 Add integration tests: imported fragment YAML can reference `template_vars`
- [ ] 5.3 Add integration tests: workflow YAML can template `workflow.options.max_concurrency`
- [ ] 5.4 Run SSOT gates: `just openspec-check` and `just qa`

