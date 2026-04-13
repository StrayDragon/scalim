## 1. Align SSOT

- [x] 1.1 将 `justfile:test-gate` 的 `--cov-fail-under` 提升到 100（并保持与 spec 一致）
- [x] 1.2 将 `openspec/specs/testing-quality/spec.md` 的覆盖率门槛提升到 100，并更新 rationale

## 2. Optional drift guard

- [x] 2.1 在 `tests/governance/test_cov_fail_under_drift.py` 中添加漂移检测测试（保持）

## 3. Coverage backfill (threshold=100)

- [x] 3.1 回填缺失覆盖率：补齐未覆盖路径或为不可达分支添加显式 `no cover` 治理，确保 `--cov-fail-under=100` 可通过

## 4. Verification

- [x] 4.1 Run `just test-gate` / `just qa` to verify
- [x] 4.2 Run `just openspec-check` to validate artifacts
