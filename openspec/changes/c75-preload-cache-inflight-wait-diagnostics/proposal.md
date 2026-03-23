## Why

在引入 `PreloadCache.get_or_load()` 的 inflight 去重（`preload-cache-inflight-dedupe`）之后，“持锁执行用户 `load_fn`”的死锁风险可被消除，但仍存在一个现实问题：当 `load_fn` 因外部依赖（网络/I/O/第三方库）长时间阻塞时，同 key 的等待方会无限期挂起，CI/服务会表现为“偶发卡死”，且缺少明确诊断线索。

需要一套**默认不改变行为**、但在发生长时间等待时能提供**稳定、可 grep、可观测**诊断信号的能力，帮助快速定位是哪个 `source_id` 的 preload 被卡住，以及卡在哪里/卡多久。

## What Changes

- 为 preload cache 的 inflight 等待引入“可选诊断能力”（默认关闭，不影响现有语义）：
  - 当等待 inflight 超过阈值时，输出一次或周期性 warning（含稳定字段：`source_id`、`wait_s`、`owner_thread_ident` 等）
  - 可选记录创建 inflight 的调用点信息（例如精简 stack/函数名），用于定位是哪个 loader 触发了挂起（需可配置，默认不采样，避免性能/隐私风险）
- 提供明确的“调试/测试模式”开关（例如环境变量或 runtime 选项）：
  - 仅在显式开启时，对超长等待给出更强的诊断（例如更频繁的 warning，或在极端情况下抛出带诊断信息的异常）
  - 默认模式下不引入 timeout/抛错，避免对用户正常长耗时 loader 造成误伤
- 新增/调整测试以覆盖诊断信号的稳定性（仅在开启诊断模式时断言日志/事件），并确保不会引入新的测试不稳定性（仍以 `join(timeout=...)` 防卡死）。

## Recommended Decisions (SSOT)

- 开关 SSOT：优先 runtime option（显式参数注入），默认关闭；不通过环境变量隐式改变框架行为。
- 日志格式：遵循 `[scalim] preload-cache:` 前缀与稳定 `k=v` 字段，便于 grep/聚合告警。
- 极端 fail-fast（timeout/抛错）不在本变更实现范围内；如需要，后续用单独 change（仅 proposal.md）定义。

## Sequencing / Dependencies

- 建议与 `preload-cache-concurrent-load-scenarios` 搭配：前者负责边界澄清与复现口径，本变更提供“等待过长时如何定位”的稳定诊断信号。

## Capabilities

### New Capabilities
- `preload-cache-inflight-wait-diagnostics`: 定义 preload inflight 等待的可选诊断信号（阈值、字段、默认关闭与显式开启原则）。

### Modified Capabilities
- `source-cache`: 补充并发/诊断要求：当 preload inflight 等待异常偏长时，系统应提供可选的诊断信号以协助排障（默认不改变语义）。
- `framework-logging`: 补充一个约定场景：preload cache 的等待告警应遵循 `[scalim] <subsystem>:` 前缀与稳定 `k=v` 字段输出，便于下游监控聚合。

## Impact

- 受影响代码：
  - `src/scalim/execution/preload_cache.py`（inflight 数据结构与 wait 路径）
  - `src/scalim/_internal/loggingx.py`（如需新增子系统 logger 入口或字段约定）
- 运行时影响：
  - 默认关闭时，行为与性能应保持不变
  - 显式开启诊断时，会有额外日志与（可选）少量 stack 采样开销
