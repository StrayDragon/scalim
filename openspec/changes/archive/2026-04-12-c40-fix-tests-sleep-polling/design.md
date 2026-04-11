## Context

时间相关测试是 CI flaky 的高发点，尤其在 xdist 并行 + coverage 插桩 + 共享 runner 抢占严重时：

- `time.sleep(0.01/0.05)` 的实际睡眠时间可能远大于期望
- “0.3s 内不应发生某事”这类微小阈值断言容易被调度抖动污染
- 通过轮询共享列表（例如 `instrumentation.events`）+ 频繁 sleep 的 busy-wait 模式，既浪费资源又缺少失败诊断

本变更聚焦修复代表性点位（`tests/workflow/test_workflow_resources_coverage.py` 中的 wait diagnostics 相关测试），目标是验证“告警发出/等待逻辑”的语义，而不是验证极小 wall-clock 时间窗。

约束：

- fix-0：只改测试与测试 scaffolding，不改变被测语义
- 复用仓库已有的测试超时 SSOT（例如 `CI_TIMEOUT_S` / `NEGATIVE_TIMEOUT_S`）

## Goals / Non-Goals

**Goals:**

- 消除 `sleep` + 轮询导致的 flaky
- 让等待/告警断言以“显式事件信号”驱动，可重复且失败可诊断
- 避免用微小阈值（例如 `warn_after_s=0.3`）做长期断言

**Non-Goals:**

- 不引入可控 clock/freezegun 作为 Phase 0 依赖（复杂度更高，且 `time.monotonic` 的 patch 语义与覆盖面需要额外治理）
- 不扩展被测代码的对外 API，仅在测试 double / instrumentation stub 上做最小增强

## Decisions

### 1) 用事件驱动替代轮询（方案 A）

在测试 scaffolding 中扩展 `_Instrumentation.emit(...)`（或等价测试 double）：

- 当 `event_type == EVENT_DIAGNOSTIC_WARNING`（或匹配目标告警事件）时，同时 `warning_event.set()`
- 测试用例通过 `warning_event.wait(timeout=CI_TIMEOUT_S)` 等待告警出现，而不是轮询 `instrumentation.events` + `sleep(0.01)`

该方案的收益：

- 等待逻辑不再依赖 sleep，且不会 busy-wait
- 超时失败时可输出已收集事件数量/最近事件，便于定位“为什么没出现”

### 2) 避免微小阈值的“不会发生”断言（方案 B）

对“在 warn_after 之前不应 emit warning”的测试：

- 将 `warn_after_s` 提升到更宽裕、可配置的阈值（至少秒级；必要时直接使用 `CI_TIMEOUT_S`）
- 用 `Event/Barrier` 协调同步点：确保被测 wait loop 已进入等待状态后再触发 `done.set()`，避免依赖 `sleep(0.05)` 推进时序

这样仍能覆盖语义（不会过早告警），但不把断言绑死在 0.3s 这类紧阈值上。

## Risks / Trade-offs

- **测试 scaffolding 更复杂**：引入事件信号与诊断输出，但改动集中、可复用，整体维护成本下降。
- **失去“精确边界”覆盖**：Phase 0 不做虚拟时间/可控 clock，因此不追求毫秒级边界测试；若未来需要覆盖更精细时间边界，再引入可控 clock（方案 C）作为单独变更。

## Migration Plan

- Phase 0：将相关测试迁移为事件驱动等待 + 宽裕阈值 + 明确同步点；在失败时输出诊断信息
- 后续（可选）：若出现必须覆盖时间边界的需求，再评估引入可控 clock（优先局部 monkeypatch，而不是全局 freezegun）

## Governance Gate

为避免回归到 sleep/polling 模式，本 change 建议与 c35 的“测试时间相关 gate”合并落地：在 `just quick-check-only-py` 的 fail-fast 阶段扫描 `tests/**`，禁止新增 `time.sleep(...)` 推进时序与轮询等待（允许通过显式 allow 标记做局部豁免）。

## Open Questions

- 无。
