## Context

`openspec/specs/testing-quality/spec.md` 要求 `--cov-fail-under=100`，`justfile:test-gate` 使用 `--cov-fail-under=99`。两者必须对齐。

约束：
- 覆盖率门禁是 CI/QA 的硬性质量关卡
- 过高的阈值可能导致频繁误报；过低的阈值放行缺陷

## Goals / Non-Goals

**Goals:**
- 对齐 spec 和 justfile 中的覆盖率阈值为同一个值
- 建立 SSOT 机制防止再次漂移

**Non-Goals:**
- 不讨论应该是 99 还是 100（留给实施时根据实际覆盖率决定）

## Decisions

### 1) 将 spec 调整为 99 并记录原因

**理由：** `--cov-fail-under=100` 在实践中过于严格——vendor 兼容层、平台特定分支、defensive `except` 等可能导致个别行无法覆盖。99% 是更务实的门禁，同时仍保持极高的覆盖率标准。

若当前实际覆盖率 > 99.5%，可考虑提升到 100 并配合 `# pragma: no cover` 对合理的不可覆盖行做标注。

### 2) 漂移检测

在 `tests/governance/` 中添加测试，读取 `justfile` 中 `test-gate` 的 `--cov-fail-under` 值，与 `openspec/specs/testing-quality/spec.md` 中的声明值比对。

## Risks / Trade-offs

- 降到 99 可能被视为"降低标准"，但实质上是对齐到当前实际运行的门禁。

## Migration Plan

- 更新 `openspec/specs/testing-quality/spec.md`
- 添加治理测试
- 验证：`just qa`

## Open Questions

- 无。
