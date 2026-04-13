## Context

c35 建立了 `tests/support/testing_utils.py` 中的超时 SSOT（`CI_TIMEOUT_S=10.0`、`NEGATIVE_TIMEOUT_S=2.0`、`POLL_DEADLINE_S=5.0`），并提供了 `event_wait`、`barrier_wait`、`join_or_fail`、`future_result` 等 helper。部分测试已迁移，但仍有遗漏。

约束：
- 超时值必须统一管理，支持 CI 环境通过环境变量调整
- 不能破坏已有测试的语义

## Goals / Non-Goals

**Goals:**
- 将所有 `tests/` 下的硬编码超时值替换为 SSOT 常量/helper
- 统一 `wait(timeout=...)` 模式为 `event_wait(...)` / `future_result(...)` helper

**Non-Goals:**
- 不改变超时的默认数值（10s/2s/5s 足够）
- 不改变 helper 本身的实现

## Decisions

### 1) 逐文件替换

已识别的需修改文件：

| 文件 | 当前模式 | 修改为 |
|------|---------|--------|
| `test_workflow_cache_pool.py` | `_TIMEOUT_S = 5.0`、`wait(timeout=0.1)` | `CI_TIMEOUT_S`、`event_wait(...)` |
| `test_viz_hook.py` | `time.sleep` + 硬编码超时 | `event_wait` / `CI_TIMEOUT_S` |
| `test_workflow_entrypoints_smoke.py` | `30.0` | `CI_TIMEOUT_S` 或 `CI_TIMEOUT_S * 3`（长流程场景） |

### 2) 对确需非标准超时的场景

使用 `CI_TIMEOUT_S` 的倍数（如 `CI_TIMEOUT_S * 3`），而非硬编码，确保 CI 环境可统一调整。

## Risks / Trade-offs

- 极低风险：仅替换常量值，不改变测试逻辑。

## Migration Plan

- 按文件修改
- 验证：`just test-gate`

## Open Questions

- 无。
