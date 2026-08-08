## 1. Contracts & schema

- [ ] 1.1 Add live spec capability `observability-run-stats` (Branch-bound): run_stats v1 fields, nodes[] snapshot rules, profile set, high-impact warn MUST
- [ ] 1.2 Amend `performance-observability` / viz sibling notes: workflow shared-observer reset MUST NOT be presented as full-run truth; write attribution deferred to c55
- [ ] 1.3 Document schema SSOT (dataclass) + JSON wire; no required new PyPI deps; psutil optional fail-fast for memory

## 2. Accumulator & profiles (vertical)

- [ ] 2.1 Implement workflow-aware stats accumulator (PIPELINE_END snapshots → `nodes[]` + aggregate) on existing EventTypes only
- [ ] 2.2 Implement `bench` / `bench_plus` / `debug` profile factories; baseline = empty components
- [ ] 2.3 Emit high-impact warnings when relation / operator_span / viz-trace / heavy batch dump enabled
- [ ] 2.4 Optional: write `run_stats.json` sibling next to viz run dir; optional `meta.viz.run_stats` path ref only

## 3. Tests (seams confirmed)

- [ ] 3.1 Public seam: dual-demand workflow + shared observers → `run_stats.nodes` length ≥ 2; detail node retains loader (and relation snapshot if debug) non-empty after metrics finishes
- [ ] 3.2 Public seam: baseline vs bench → CSV row count / content hash equal
- [ ] 3.3 Public seam: enabling relation/debug emits warning
- [ ] 3.4 Keep `.tmp/obs-demo` as evidence harness pointer (not required in package)

## 4. Docs

- [ ] 4.1 Doc: how to read stages/loaders/nodes; observation-tax vs baseline; warn that write stage attribution lands in c55
