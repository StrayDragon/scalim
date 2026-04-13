## Context

覆盖率门禁阈值由 `openspec/specs/testing-quality/spec.md` 与 `justfile:test-gate` 共同声明并必须保持一致(SSOT)。

本次变更将覆盖率阈值提升为 `--cov-fail-under=100` 并确保该门禁可以稳定通过。

约束：
- 覆盖率门禁是 CI/QA 的硬性质量关卡
- 过高的阈值可能导致频繁误报；过低的阈值放行缺陷

## Goals / Non-Goals

**Goals:**
- 对齐 spec 和 justfile 中的覆盖率阈值为同一个值(100)
- 建立 SSOT 机制防止再次漂移

**Non-Goals:**
- 不改变核心模块定义/覆盖率统计范围

## Decisions

### 1) 统一阈值为 100，并在 gate 中强制执行

**理由：** 把“未覆盖路径”视为质量债务并强制清零；对于确实不可达/不可覆盖的防御性分支，使用显式 `# pragma: no cover` + `# pragma: allow-no-cover <reason>` 进行治理。

### 2) 漂移检测

在 `tests/governance/` 中添加测试，读取 `justfile` 中 `test-gate` 的 `--cov-fail-under` 值，与 `openspec/specs/testing-quality/spec.md` 中的声明值比对。

## Risks / Trade-offs

- 降到 99 可能被视为"降低标准"，但实质上是对齐到当前实际运行的门禁。

## Migration Plan

- 更新 `openspec/specs/testing-quality/spec.md` 与 `justfile:test-gate`
- 回填缺失覆盖率(测试补齐/必要时 no-cover 治理)
- 验证：`just test-gate`、`just qa`

## Open Questions

- 无。
