## 1. Contracts & schema

- [x] 1.1 Add live spec capability `observability-run-stats` (Branch-bound): run_stats v1 fields, nodes[] snapshot rules, profile set, high-impact warn MUST
- [x] 1.2 Amend `performance-observability` / viz sibling notes: workflow shared-observer reset MUST NOT be presented as full-run truth; write attribution deferred to c55
- [x] 1.3 Document schema SSOT (dataclass) + JSON wire; no required new PyPI deps; psutil optional fail-fast for memory

## 2. Accumulator & profiles (vertical)

- [x] 2.1 Implement workflow-aware stats accumulator (PIPELINE_END snapshots → `nodes[]` + aggregate) on existing EventTypes only
- [x] 2.2 Implement `bench` / `bench_plus` / `debug` profile factories; baseline = empty components
- [x] 2.3 Emit high-impact warnings when relation / operator_span / viz-trace / heavy batch dump enabled
- [x] 2.4 Optional: write `run_stats.json` sibling next to viz run dir; optional `meta.viz.run_stats` path ref only

## 3. Tests (seams confirmed)

- [x] 3.1 Public seam: dual-demand workflow + shared observers → `run_stats.nodes` length ≥ 2; detail node retains loader (and relation snapshot if debug) non-empty after metrics finishes
- [x] 3.2 Public seam: baseline vs bench → CSV row count / content hash equal
- [x] 3.3 Public seam: enabling relation/debug emits warning
- [x] 3.4 Pin reproducible harness under archive `mvp/`；`.tmp/obs-demo` JSON-only for viz

## 4. Docs

- [x] 4.1 Doc: how to read stages/loaders/nodes; observation-tax vs baseline; warn that write stage attribution lands in c55
