## Meta

- Type: `fix-0`
- Topic: 测试中 `time.sleep()` 与轮询等待导致的 flaky（建议事件驱动/更大裕量/可控 clock）
- Related code (代表性点位):
  - `tests/workflow/test_workflow_resources_coverage.py:1096`~`:1111`
    - `test_wait_for_inflight_done_does_not_emit_warning_before_warn_after`：`sleep(0.05)` + `warn_after_s=0.3`
  - `tests/workflow/test_workflow_resources_coverage.py:1168`~`:1175`
    - 轮询 `instrumentation.events` + `sleep(0.01)` 等 warning 出现

## 背景

时间相关的测试最容易 flaky，尤其在：

- xdist 并行；
- coverage 插桩；
- CI 抢占严重（共享 runner）；

时，`sleep(0.01/0.05)` 与 “0.3s 内不应发生某事”这类断言会被调度抖动污染。

这里的测试目标是验证“告警发出/等待逻辑的语义”，而不是验证“必须在某个极小 wall-clock 窗口内完成”。

## 现状与问题

### 问题 1：用 `sleep` 推进时序并做微小阈值断言

`test_wait_for_inflight_done_does_not_emit_warning_before_warn_after`：

- 设置 `warn_after_s=0.3`
- 子线程 `sleep(0.05)` 后 `done.set()`
- 断言：不会出现 warning

在慢机器/高负载下，`sleep(0.05)` 实际可能远大于 0.05；加上线程调度，可能逼近或超过 0.3，导致 warning 偶发出现并使测试失败。

### 问题 2：轮询共享列表 + 频繁 sleep

另一类用例通过轮询 `instrumentation.events` 列表等到某个事件出现：

```py
while time.monotonic() < deadline:
    warnings = [...]
    if warnings: break
    time.sleep(0.01)
assert warnings
```

该模式的问题：

- 不必要的 busy-wait；
- deadline 太紧时易 flaky；
- 超时失败时缺少诊断信息（为什么没出现？线程卡哪？）。

## 目标

- 消除这类时间敏感 flaky；
- 让测试失败时更易诊断；
- 不改变被测语义（依然覆盖 warning emission / wait loop）。

## 推荐修复方案

### 方案 A：用事件驱动替代轮询（推荐）

做法：

- 扩展测试内的 `_Instrumentation.emit`：当 event_type == `EVENT_DIAGNOSTIC_WARNING` 时，同时 `warning_event.set()`。
- 测试里用 `warning_event.wait(timeout=CI_TIMEOUT_S)` 等待，而不是轮询列表。

优点：

- 不再依赖 `sleep(0.01)`；
- 失败时可以打印 “当前已收集事件数/最近事件” 更容易定位。

缺点：

- 需要改少量测试 scaffolding（但集中且可复用）。

### 方案 B：避免用微小阈值做“不会发生”断言（推荐）

做法：

- 将 `warn_after_s=0.3` 提升到更宽裕的值（例如 `warn_after_s=CI_TIMEOUT_S` 或至少 2s 级别），并将 `done.set()` 的触发更快且更确定：
  - 用 `Event`/`Barrier` 协调“等待逻辑已进入 wait 循环”后再 set done；
  - 或直接在主线程 set done，不依赖 sleep。

优点：

- 仍然验证“不会在 warn_after 之前发 warning”，但避免把断言绑在 0.3s 这种紧阈值上。

缺点：

- 需要梳理 test 的同步点（但不会太难）。

### 方案 C：可控 clock（高级方案，非必须）

做法：

- monkeypatch `resources_base_mod.time.monotonic` / `time.time` 为可控函数；
- 通过推进虚拟时间触发/避免 warning。

优点：

- 完全消除 wall-clock 抖动；
- 可精确覆盖边界条件。

缺点：

- 实现复杂度更高（需要确保被测代码只用 patched clock）。

## 推荐方案

Phase 0（fix-0）推荐落地 **方案 A + 方案 B**：

- A 解决轮询 flaky；
- B 解决小阈值 sleep flaky；

方案 C 只在未来确实需要覆盖更精细时间边界时再引入。

关于 `freezegun`：

- Phase 0 不建议引入全局 `freezegun`（会扩大依赖与 patch 面，且对 `time.monotonic` 的覆盖需要额外治理）。
- 若未来确需覆盖更精细时间边界，优先采用**局部**可控 clock（例如仅 monkeypatch 被测模块的 `time.monotonic`），保持 scope 小且可审计。

治理补强（推荐与 c35 合并落地）：

- 增加轻量 gate，禁止测试回归到 `sleep/polling` 与硬编码小阈值（允许显式 allow 标记做局部豁免）。

## 性价比

- 成本：低到中（只改测试，且改动集中在少数文件）。
- 收益：高（CI 稳定性提升、减少重跑与排障成本）。

## 验证建议

- 在默认 pytest 配置下重复运行相关测试 20 次：
  - `pytest -q tests/workflow/test_workflow_resources_coverage.py -k wait_diagnostics`
- 观察：不再出现偶发 timeout/断言失败。
