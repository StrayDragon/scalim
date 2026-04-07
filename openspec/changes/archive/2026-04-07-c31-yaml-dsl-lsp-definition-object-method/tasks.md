## 1. Editor Semantics Core: `obj.method` Static Inference

- [x] 1.1 Extend Python definition resolution to return multiple ordered `PythonDefinitionLocation` results (primary resolved symbol, then fallback locations)
- [x] 1.2 Implement module-level `Assign/AnnAssign` inference for `module:obj.method`:
  - handle `obj: Klass = ...`
  - handle `obj = Klass()` (Name/Attribute callee)
  - handle `obj = Klass` (class alias)
- [x] 1.3 Implement minimal import following for inference (AST-only, single-hop):
  - `from pkg.mod import Klass as K`
  - `import pkg.mod as m` + `m.Klass`
- [x] 1.4 Ensure resolved `symbol_path` reflects the actual target (e.g. `Klass.a_method`), and inference uncertainty produces actionable warnings (no crashes)

## 2. LSP Server: Multi-Location Go-to-Definition

- [x] 2.1 Verify LSP `textDocument/definition` handler returns all locations from core in stable order (no dedupe/reorder surprises)
- [x] 2.2 Add/adjust “解释 Python 引用解析失败”输出：在多 locations 场景下能展示 primary + fallback（无需执行用户代码）

## 3. Fixtures + Regression Tests (Coverage Matrix)

- [x] 3.1 Add core unit tests covering `module:obj.method` resolution:
  - same-module `obj = Klass()`
  - same-module `obj: Klass = ...`
  - cross-module `from ... import Klass` + `obj = Klass()`
  - cross-module `import ... as m` + `obj = m.Klass()`
  - degrade cases: `obj = factory()` / import target missing → empty or fallback + warnings
- [x] 3.2 Add LSP server integration test: YAML `loader: "pkg.mod:obj.method"` returns ≥2 LSP Locations with primary pointing to `Klass.method`
- [x] 3.3 Add regression assertions for deterministic ordering (primary-first) and for “no crash + warnings” failure modes

## 4. Validation

- [x] 4.1 Run `just openspec-check` to validate new change artifacts
- [x] 4.2 Run focused pytest suite for changed areas (core semantics + LSP server MVP tests)
