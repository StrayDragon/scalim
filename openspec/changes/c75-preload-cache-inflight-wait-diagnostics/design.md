## Context

`PreloadCache.get_or_load(source_id, load_fn)` 目前通过 per-key 的 inflight 去重保证：

- 同一 `source_id` 在并发场景下最多一次真实执行 `load_fn`
- 其余线程成为 waiter，等待 inflight 完成并复用 value/error

该机制解决了“持锁执行用户 `load_fn`”可能导致的死锁问题，但仍存在一个现实故障模式：

- owner 线程执行 `load_fn` 长时间阻塞（网络/I/O/第三方库卡住、死循环等）
- waiter 线程在 `_get_or_load_waiter()` 内部调用 `inflight.done.wait()`，将无限期挂起
- 对外表现为 CI/服务偶发卡死，但缺少稳定、可 grep 的诊断线索

当前实现点：

- `src/scalim/execution/preload_cache.py`：
  - waiter 路径：`_get_or_load_waiter()` → `inflight.done.wait()`（无 timeout、无日志）
  - inflight 结构体包含 `owner_ident`，具备输出最小诊断字段的基础
- 日志规范工具：`src/scalim/_internal/loggingx.py`（`[scalim] <subsystem>:` + 稳定 `k=v`）

约束：

- 运行时需兼容 Python 3.6
- 默认模式下不改变语义（不新增 timeout / 抛错 / 中断等待）
- 诊断能力必须显式开启（opt-in），默认关闭且基本零开销
- 本变更不涉及生成文档/注入区块；验收以 `just qa` 与 `just openspec-check` 为准

## Goals / Non-Goals

**Goals:**

- 提供 inflight wait 的**可选诊断能力**（默认关闭）。
- 在诊断开启时，当等待超过阈值，输出稳定 warning 信号，至少包含 `source_id` 与 `wait_s`。
- 日志字段稳定、可聚合，遵循项目日志前缀约定，方便下游 grep/告警。
- 保持正常路径性能：默认关闭时不引入额外循环/时间计算。

**Non-Goals:**

- 不在默认模式引入 timeout 或抛出异常（不“误伤”合法的长耗时 loader）。
- 不将诊断能力扩展为跨进程/跨 host 的卡死检测。
- 不默认采集/输出完整 stack（隐私与性能风险）；仅作为可选项讨论。

## Decisions

### 1) 用显式配置对象控制诊断（默认关闭）

在 `PreloadCache` 内部引入一个“诊断配置”对象（例如 `PreloadCacheWaitDiagnostics`），其默认值为 disabled。

建议包含（可按实现需要精简）：

- `enabled: bool`
- `warn_after_s: float`：超过该阈值开始输出 warning
- `repeat_every_s: Optional[float]`：是否周期性输出；`None` 表示只输出一次
- `capture_owner_callsite: bool`：是否在创建 inflight 时记录轻量调用点（默认 `False`）

开启方式建议二选一（实现择其一即可）：

- **runtime option**：调用方构造 `PreloadCache(wait_diagnostics=...)` 并把实例传入 `ScalimEngine(..., preloaded_cache=cache)`
- **环境变量**：仅作为调试手段（例如 `SCALIM_PRELOAD_CACHE_WAIT_DIAGNOSTICS=1`），避免为库用户强制引入新 API

### 2) waiter 路径改为“可观测但不改语义”的等待循环

当 `enabled=False`：保持当前实现 `inflight.done.wait()`（无循环、无日志）。

当 `enabled=True`：改为循环等待：

- 使用 `time.monotonic()` 记录 `wait_start`
- `inflight.done.wait(timeout=interval)`：
  - `interval` 可取 `min(1.0, warn_after_s)` 的一类小值，或基于 `repeat_every_s` 推导
  - 每次 timeout 后计算 `wait_s`
  - 当 `wait_s >= warn_after_s` 时输出 warning（一次或周期性）
- 一旦 `done` 被 set，立即按现有逻辑返回/抛错（保持语义一致）

### 3) 诊断信号采用 `loggingx` 的稳定格式

- logger：`loggingx.get_logger("preload-cache")`
- message：`loggingx.prefix("preload-cache") + "inflight wait slow: " + loggingx.format_kv(...)`
- 字段至少包含：
  - `source_id`
  - `wait_s`
- 建议追加稳定字段（不影响 spec 的最小要求）：
  - `owner_thread_ident`（来自 `_InFlight.owner_ident`）
  - `waiter_thread_ident`（来自 `threading.get_ident()`）
  - `warn_after_s`、`repeat_every_s`
  - `owner_callsite`（仅当 `capture_owner_callsite=True` 时）

### 4) 测试策略以“开启诊断时断言日志”为主

在 `tests/test_preload_cache.py` 补充覆盖：

- 默认关闭：并发等待不会产生 warning（避免噪音）。
- 显式开启：构造一个会 sleep 的 loader，使 waiter 等待超过很小阈值；用 `caplog` 断言出现一条包含稳定字段的 warning。
- 防卡死：仍以 `join(timeout=...)` + `Barrier(timeout=...)` 的方式保证测试不会挂死。

## Risks / Trade-offs

- [风险] 周期性 warning 可能在真实长耗时任务中产生噪音。
  → 缓解：默认关闭；阈值与周期可配置；默认只输出一次。

- [风险] 等待循环会比一次性 `wait()` 有更多 wake-up。
  → 缓解：仅在启用诊断时生效；interval 选择保守（例如 1s 或更大）。

- [风险] 输出调用点/stack 可能包含敏感信息。
  → 缓解：默认不采集；采集时仅保留精简信息（函数名/文件名），并明确这是调试模式能力。

## Migration Plan

1. 实现 `PreloadCache` 的诊断配置结构与 waiter 循环等待。
2. 接入 `loggingx` 输出稳定 warning（满足 `source_id`/`wait_s` 最小字段要求）。
3. 增加测试覆盖默认关闭与显式开启两条路径。
4. 验收：`just qa` + `just openspec-check`。

## Open Questions

- 诊断开关的 SSOT 选择：优先 runtime option 还是环境变量？（可先实现 runtime option，环境变量后续补充）
> 优先 runtime option
- 是否需要“极端调试模式”支持 fail-fast（等待超过更大阈值时抛异常）？该能力与默认语义冲突，建议后续单独变更。
> 可以给后置提案 c700- 然后仅proposal.md 即可
