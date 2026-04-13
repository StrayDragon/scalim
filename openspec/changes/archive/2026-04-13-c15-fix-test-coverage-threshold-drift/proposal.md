## Why

覆盖率门禁是 CI/QA 的硬性质量关卡。当前项目需要将覆盖率阈值提升为 `--cov-fail-under=100` 并作为 SSOT 强制执行；同时确保 spec/命令/治理测试不会出现漂移。

## What Changes

- 对齐规范与实现：将 `openspec/specs/testing-quality/spec.md` 与 `justfile:test-gate` 的 `--cov-fail-under` 统一为 100。
- 明确 SSOT：规范中的阈值必须与 `justfile:test-gate` 保持一致；若未来调整阈值，必须同步更新两处并记录简要理由。
- 回填覆盖率：补齐缺失的测试覆盖(必要时对不可达分支做显式 `no cover` 治理)以确保门禁可落地。
- 保留/补强漂移治理测试，确保阈值不会再次出现规范与实现不一致。

## Capabilities

### New Capabilities

### Modified Capabilities
- `testing-quality`: 覆盖率阈值提升到 100，并通过 SSOT + 治理测试锁定一致性。

## Impact

- 文件：`justfile`、`openspec/specs/testing-quality/spec.md`。
- `--cov-fail-under=100` 会要求补齐剩余未覆盖的路径；不达标时 `just test-gate`/`just qa` 将失败。
