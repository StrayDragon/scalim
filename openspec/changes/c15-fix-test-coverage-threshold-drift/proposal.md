## Why

OpenSpec 规范 `testing-quality/spec.md` 要求核心覆盖率 `--cov-fail-under=100`，但 `just test-gate` 实际使用 `--cov-fail-under=99`。规范与实现的漂移会导致质量门禁失去信号意义——要么规范过高不切实际，要么门禁过低放行了不该通过的代码。

## What Changes

- 对齐规范与实现：将 `justfile` 中 `test-gate` 的 `--cov-fail-under` 值提升到 100（与 spec 一致），或者将 spec 调整到 99 并补充说明原因。
- 在 `openspec/specs/testing-quality/spec.md` 中增加 SSOT 标记：`cov-fail-under` 的值必须与 `justfile:test-gate` 保持一致。
- 可选：添加漂移检测脚本（类似现有治理测试模式）。

## Capabilities

### New Capabilities

### Modified Capabilities
- `testing-quality`: 覆盖率阈值 SSOT 对齐与漂移检测。

## Impact

- 文件：`justfile`、`openspec/specs/testing-quality/spec.md`。
- 若提升到 100%，可能需要补充少量缺失的测试覆盖。
