## 1. Compute decimal contract

- [x] 1.1 Extend top-level derived field runtime type gates so `fields.*.(compute|call_by)` accept `Decimal` as a valid `FieldValue`.
- [x] 1.2 Add compute builtin `dec(x)` with explicit `None/bool/int/float/str/Decimal` semantics and fail-fast handling for invalid strings / non-finite floats.
- [x] 1.3 Ensure every YAML expression surface that reuses `SecureComputeEngine` sees the same `dec(x)` builtin without introducing implicit global float-to-decimal coercion.

## 2. Spec and regression coverage

- [x] 2.1 Add `field-compute` delta specs for `dec(x)` and for top-level `compute/call_by` returning `Decimal`, keeping the `xlsx_memory` preservation concern out of this change.
- [x] 2.2 Add focused tests for `dec(...)` conversions, top-level `fields.*.compute` returning `Decimal`, and top-level `fields.*.call_by` returning `Decimal`.
- [x] 2.3 Keep SSOT in `openspec/changes/c1-yaml-compute-decimal/*` and `openspec/specs/field-compute/spec.md`; if docs/spec indexes or injected blocks need refresh, use `just gen-docs`, then validate with `just openspec-check` and the smallest relevant pytest subset.
