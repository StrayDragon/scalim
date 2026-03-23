## Why

近期围绕 `cache_mode=preload_forever` 的“同一个 load 是否可能被不同线程同时触发”出现理解偏差：

- Scalim **单个** `ScalimEngine` 实例的 `run()` 有实例级锁保护，不会在同一实例内并发进入 preload 阶段。
- 但在两类场景下，**同一个缓存 key 的 load** 仍然可能被并发触发：  
  A) 多线程并发多个 `ScalimEngine.run()`，且它们**共享同一个** `preloaded_cache` 容器；  
  B) workflow 多节点并发运行，多个 node 可能同时请求 workflow-scope 的同一 `cache_pool` 条目（同一 signature）。

如果边界不清晰，会导致两类风险：

- **性能误判**：认为永远不会并发 → 忽略 stampede（重复 I/O/重复计算）与排队等待的尾延迟。
- **正确性风险**：把 `preloaded_cache` 当作跨不同配置/不同 signature 的“长期缓存”复用，可能产生错误复用（尤其当 key 仅是 `source_id` 时）。

本变更作为延后 issue：先把并发场景、复现方式与边界定义清楚，避免后续继续“靠口头约定”推进。

## What Changes

- 明确“同一个 load”的定义与 key 空间差异：
  - `PreloadCache.get_or_load(source_id, load_fn)`：key 为 `source_id`（不包含 loader/params/normalize signature），语义定位为**仅 in-flight 去重**。
  - `WorkflowCachePool.get_or_load(signature, ...)`：key 为完整 signature（包含 params/normalize 等），用于 workflow-scope 的正确复用。
- 文档化并发边界（哪些路径会并发、哪些不会）并给出可运行的复现步骤：
  - A) 多 `ScalimEngine` 并发共享 `preloaded_cache`
  - B) workflow 多 node 并发请求同一 signature
- 列出“可能导致错误”的重叠/复用条件（用于后续判断是否需要更强护栏或签名化 key）。

### 复现：A) 多线程并发多个 `ScalimEngine.run()` 且共享同一个 `preloaded_cache`

前提说明：

- 同一 `ScalimEngine` 实例不会并发 `run()`（实例锁保护），因此需要 **多个 engine 实例** 或 **多个并发 `run_ir(...)` 调用**。
- preload 阶段的真实调用点在 `Pipeline._preload_cached_sources`：当 `runtime.preloaded_cache` 提供 `get_or_load` 时会调用之。

最小可验证复现（等价于 engine preload 路径的并发窗口）：

- 运行单测：`pytest -q tests/test_preload_cache.py::test_preload_cache_get_or_load_returns_cached_value_inside_lock`
  - 两个线程同时对同一 `source_id` 调用 `PreloadCache.get_or_load(...)`
  - 断言 `load_fn` 只会被调用一次（in-flight 去重）

补充（常见误用）：

- 若共享的 `preloaded_cache` 是普通 `dict`，并发下行为未定义（可能重复 load、或出现竞态读写）。
- 若跨不同 demand/不同上下文复用同一个 `PreloadCache`，且同名 `source_id` 实际对应不同 loader/params/normalize，则存在**错误复用**风险（因为 key 不包含 signature）。

### 复现：B) workflow 多节点并发，走 `WorkflowCachePool` 的同一 signature

workflow runner 本身使用 `ThreadPoolExecutor(max_concurrency)` 并发执行 nodes；当启用 `workflow.options.cache_pool` 且多个 nodes 请求同一条目（同一 signature）时，会并发进入 `WorkflowCachePool.get_or_load(...)`。

使用仓库现成 fixture 可复现：

- workflow YAML：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture_cache_pool_pin.yaml`
  - `max_concurrency: 2`
  - 两个 runs 都引用同一个 demand：`workflow_fixture_demand.yaml`
  - demand 中包含 `sources.preload_counter.cache_mode: preload_forever`
- Python 入口（参考 `docs/doc/yaml-dsl/workflow.md`）：
  - `from scalim.dsl.by_yaml import run_workflow`
  - 运行上述 workflow 文件，并开启 observer/日志以观测 `workflow_cache_acquire` 等事件

预期现象：

- 两个 node 在 preload 阶段并发请求同一 signature
- cache pool 对同一 signature 应复用同一 entry：同一时刻最多一个 `load_fn` 执行，其余等待并复用结果

## Capabilities

### New Capabilities
- `preload-cache-concurrent-load-scenarios`: 定义 preload cache / workflow cache pool 的并发触发场景、key 空间与“只做 in-flight 去重”的默认语义，并给出可运行复现步骤。

### Modified Capabilities
- `source-cache`: 明确 `preloaded_cache` 的并发边界与复用约束（共享容器需要线程安全；跨不同 signature 复用 `source_id` key 可能错误）。
- `workflow-cache-pool`: 明确并发下“同一 signature in-flight 去重”的期望，以及冲突策略 `error|warn|separate` 对重复加载的影响（不同 signature 允许并行存在但不得错误复用）。

## Impact

- 受影响代码路径（用于后续实现/验证）：
  - `src/scalim/execution/pipeline/base/pipeline.py`（preload_forever 调用点 + cache_pool 优先级）
  - `src/scalim/execution/preload_cache.py`（`PreloadCache.get_or_load` key/语义）
  - `src/scalim/execution/workflow_cache_pool.py`（signature-based 去重与冲突策略）
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`（workflow 并发执行模型）
- 后续需要验证/澄清的点（当前先记录，不在本 change 中实现）：
  - “错误复用”边界：当共享 `PreloadCache` 跨不同配置复用时，是否需要签名化 key、或增加 guardrail（例如显式标注 share scope / trusted mode）。
  - “重叠导致错误”的判定标准：loader 非幂等/有副作用时，重复加载属于性能问题还是正确性问题；是否需要在文档中明确“loader SHOULD be idempotent”一类约束。
