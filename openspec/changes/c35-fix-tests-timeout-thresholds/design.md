## Context

仓库测试默认运行方式较重（xdist 并行 + coverage），在 CI 高负载环境下会放大：

- 线程调度延迟与启动抖动
- import/coverage 插桩开销
- I/O 竞争

目前若干并发/线程安全相关测试在同步点上使用了 `timeout=1.0/2` 这类紧凑的 wall-clock 阈值（Barrier/Event/Future 等）。这类测试的意图通常是验证并发语义本身（去重、无死锁、可重入、等待诊断等），而不是验证“必须在 1 秒内完成”。将断言绑定到极小超时会把 CI 抖动误当成业务失败，从而形成 flaky。

仓库已经存在统一超时常量（`tests/support/testing_utils.py` 中的 `CI_TIMEOUT_S` / `NEGATIVE_TIMEOUT_S`），且支持通过环境变量调节（例如 `SCALIM_TEST_TIMEOUT`）。本变更需要把散落在测试中的小超时收敛到该 SSOT，并在真正超时时输出足够诊断信息以降低排障成本。

## Goals / Non-Goals

**Goals:**

- 消除因 `timeout=1.0/2` 等过小阈值导致的偶发 flaky
- 保持测试覆盖目标不变：仍验证并发行为/线程安全语义，而不是验证时间阈值
- 超时阈值可配置（CI 与本地可不同），并在超时发生时提供明确诊断（线程栈/状态）

**Non-Goals:**

- 不改变生产代码行为（仅调整测试与测试支持工具）
- 不把所有测试都“无限等待”；仍需有上限并在死锁时 fail-fast

## Decisions

### 1) 收敛正向等待超时到 `CI_TIMEOUT_S`，负向断言使用 `NEGATIVE_TIMEOUT_S`

对并发测试中的同步等待统一口径：

- 正向等待（期望会完成）：Barrier/Event/Future 等的 `timeout` 统一使用 `CI_TIMEOUT_S`（默认更宽松，且可配置）
- 负向断言（期望不会发生/不会完成）：使用 `NEGATIVE_TIMEOUT_S`（同样可配置），避免用“1 秒内必须不发生”这种脆弱断言

### 2) 引入测试侧同步 helper，超时后统一输出诊断

在 `tests/support/` 增加同步辅助函数（或扩展现有工具），对常见同步原语封装：

- `barrier_wait(...)`：捕获 `BrokenBarrierError` 并输出参与方/线程状态
- `event_wait(...)` / `future_result(...)`：超时后 dump 当前线程信息（必要时包含线程栈）

调用点统一使用 helper，从而：

- 避免各处重复写 `timeout=...` 与异常处理
- 一旦真的卡死/死锁，失败信息可直接用于定位而不是只看到“超时”

### 3) 增加轻量 gate，禁止回归到 `sleep/polling` 与硬编码小阈值

为防止后续回归：

- 增加一个可重复运行的扫描 gate（脚本或 just 任务），检查 `tests/**` 中是否出现易 flaky 模式：
  - 硬编码的极小 timeout（例如 `timeout=1.0`、`timeout=2`）
  - `time.sleep(0.01/0.05)` 驱动的轮询等待
- gate 允许通过显式 allow 标记做局部豁免（与 `cast/no-cover/dynattr` 的治理风格一致），避免误伤确有必要的用例

## Risks / Trade-offs

- **真实死锁失败更慢**：更大的 `CI_TIMEOUT_S` 可能让真正死锁的失败耗时变长；用“超时诊断 + 可配置阈值”平衡（必要时在 CI 专项任务中下调）。
- **测试代码改动面**：涉及多个测试文件的统一迁移；通过集中 helper 能降低维护成本并减少未来回归。

## Migration Plan

- Phase 0：引入 helper + 将代表性 flaky 点位（thread_safety / adaptive_tuning / yaml_dsl_lsp_cache）迁移到统一口径
- 持续治理：为新增并发测试强制使用 helper/常量（通过 review 或 lint 规则）

## Open Questions

- 无。
