## 1. Align SSOT

- [ ] 1.1 决定统一阈值（将 `justfile:test-gate` 提升至与规范一致，或将 `openspec/specs/testing-quality/spec.md` 调整为与当前门禁一致），并同时更新两处
- [ ] 1.2 若阈值低于 100%，在 `testing-quality` 主规范中补充简短 rationale

## 2. Optional drift guard

- [ ] 2.1 在 `tests/governance/` 中添加测试：读取 `justfile` 中 `test-gate` 的 `--cov-fail-under` 并与规范声明比对（按 design 可选）

## 3. Coverage backfill (if threshold raised)

- [ ] 3.1 若将门禁提高到 100%，补充缺失覆盖或对合理不可覆盖行使用受控 `pragma: no cover` 并满足现有 no-cover 治理

## 4. Verification

- [ ] 4.1 Run `just qa` / `just test-gate` to verify
- [ ] 4.2 Run `just openspec-check` to validate artifacts
