# workflow-cache-pool Specification

**状态: ✅ 已实现**

## Purpose
提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过
signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件/并发安全确保"复用正确且可诊断".

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/yaml_dsl/workflow.py` (workflow options 解析 + cache_pool 语义校验)
- `src/IMPL_ROOT/dsl/yaml_dsl/schema/workflow.gen.json` (workflow schema)
- `src/IMPL_ROOT/dsl/yaml_dsl/workflow_entrypoints.py` (`run_workflow` 创建/关闭 cache pool + node done 生命周期钩子)
- `src/IMPL_ROOT/execution/workflow_cache_pool.py` (cache pool 实现: signature/budget/refcount/pin/事件)
- `src/IMPL_ROOT/execution/pipeline/base/pipeline.py` (preload_forever 优先走 cache_pool.get_or_load)
- `src/IMPL_ROOT/events/events.py` + `src/IMPL_ROOT/events/catalog.py` (workflow cache 事件定义/注册)

## Requirements


### Requirement: workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
系统 MUST 将 workflow cache pool 的配置入口收敛到 runtime policy boundary（`workflow_runtime_options.cache_pool`），并保持对外配置面受限（preset-based）：

- workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`（出现时 MUST fail-fast 并给出迁移指引）
- 系统 MUST 提供封闭集合的 cache_pool preset（示例）：
  - `WorkflowCachePoolDisabled()`（默认）
  - `WorkflowCachePoolPreloadForeverUnlimited()`
  - `WorkflowCachePoolPreloadForeverShared(max_entries=<positive-int>, pin=...)`
- `WorkflowCachePoolPreloadForeverShared` 仅允许暴露最小 knobs（bounded + pin）：
  - `max_entries` MUST 为正整数，且 MUST 显式提供（无隐式默认值）。**BREAKING**
  - `pin` MAY 存在，用于在 bounded 场景中将指定 logical keys 常驻到 workflow_end（避免 refcount 自动释放）
- `WorkflowCachePoolPreloadForeverUnlimited` MUST 不暴露 budget/pin knobs，并且其语义 MUST 等价于：
  - `release_policy=workflow_end`（不启用 DAG refcount 自动释放）
  - 禁用 entries 数量预算检查（不强制 `max_entries` 预算护栏）
- 其余策略 MUST 固定为稳定默认（不对外暴露 knobs），例如：
  - `conflict_policy=error`
  - bounded preset: `release_policy=dag_refcount`
  - bounded preset: `budget.over_budget_policy=fail_fast`
- 旧的 `workflow.options.share_preload_cache` MUST 被拒绝（提示迁移到 `workflow_runtime_options.cache_pool` preset）

#### Scenario: cache_pool config in YAML is rejected with migration guidance
- **GIVEN** workflow YAML 包含 `workflow.options.cache_pool`
- **WHEN** 用户执行 validate/compile 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

#### Scenario: cache_pool is enabled through unlimited runtime preset
- **GIVEN** 调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverUnlimited()`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
- **AND** cache entries MUST 常驻到 workflow_end（不得在 workflow 中途因 refcount 归零而自动释放）
- **AND** 系统 MUST NOT 按 entries 数量预算对 cache pool 施加上限

#### Scenario: cache_pool is enabled through bounded runtime preset
- **GIVEN** 调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16)`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
- **AND** MUST 按 `max_entries` 预算限制 cache entries 数量

#### Scenario: bounded preset supports pin for selected logical keys
- **GIVEN** 调用方传入 `WorkflowCachePoolPreloadForeverShared(max_entries=16, pin=(WorkflowCachePoolPin(kind="preload_forever", source_id="s1"),))`
- **WHEN** `s1` 的缓存条目 refcount 归零
- **THEN** 系统 MUST NOT 释放该条目（等价常驻到 workflow_end）


### Requirement: workflow provides a cache pool with signature-based keys
系统 MUST 在一次 workflow 执行内提供 workflow-scope cache pool,用于承载可共享的缓存条目(例如 preload_forever 结果、未来的 dataset/index 工件等)。

cache pool MUST 将"可复现的 signature"纳入缓存 key,以避免复用错误数据;signature 至少应包含:
- 缓存条目 kind(例如 preload_forever / dataset_index)
- `source_id`(或 artifact id)
- loader 引用(或 artifact producer 节点信息)
- 渲染后的 params(含已解析的 `{$init_var: ...}` / `{$ctx: ...}`)
- normalize/lookup context 等会影响结果形状的关键字段

#### Scenario: same signature reuses cache entry
- **GIVEN** 两个 workflow node 请求同一个缓存条目且其 signature 完全一致
- **WHEN** cache pool 已存在该条目
- **THEN** 系统 MUST 复用该缓存结果(不得重复加载/构造)

#### Scenario: concurrent same signature triggers at most one in-flight load
- **GIVEN** workflow node A 与 node B 并发请求同一条目且 signature 完全一致
- **WHEN** 该 signature 当前为 miss
- **THEN** 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
- **AND** 其余请求 MUST 等待并复用该次 load 的结果或异常
- **Repro**: `tests/test_workflow_cache_pool.py::test_workflow_cache_pool_get_or_load_dedupes_concurrent_loads_per_signature`

#### Scenario: different signature does not reuse cache entry
- **GIVEN** 两个 workflow node 请求同一个 `source_id` 但 loader/params/normalize 不同导致 signature 不一致
- **WHEN** 两个请求先后发生
- **THEN** 系统 MUST NOT 复用错误的缓存结果

### Requirement: cache pool defines an explicit conflict policy
当多个 workflow nodes 对同一逻辑 key(例如同一个 `source_id`) 请求缓存但 signature 不一致时,系统 MUST 提供明确且可配置的冲突策略:
- `error`: fail-fast(默认/严格),并提供差异摘要
- `separate`: 允许并行存在多个 signature 的条目,互不复用
- `warn`: 继续执行但产生可观测告警(用于迁移/排障窗口)

#### Scenario: conflict policy controls behavior
- **GIVEN** node A 与 node B 请求同一个 `source_id` 且 signature 不一致
- **WHEN** 冲突策略为 `error`
- **THEN** 系统 MUST fail-fast
- **WHEN** 冲突策略为 `separate`
- **THEN** 系统 MUST 创建/保留两个互不复用的缓存条目


### Requirement: cache pool supports lifecycle management and auto-release
系统 MUST 支持 cache pool 的生命周期管理,以减少 workflow 常驻内存:
- 系统 MUST 基于 workflow DAG 推导缓存条目的 consumer set 上界,并以此初始化 refcount
- 系统 MUST 在运行时随 node 完成递减 refcount
- 当 refcount 归零时,系统 MUST 释放该缓存条目(或将其标记为可淘汰)
- 当 `release_policy=workflow_end` 或条目被 pin 时,系统 MUST 禁止按 refcount 自动释放该条目（需在 workflow 结束时统一清理）

#### Scenario: cache entry is released after last consumer finishes
- **GIVEN** 某个缓存条目只会被 node A 与 node B 消费,且 node B 为该条目的最后一个消费者
- **WHEN** node B 完成且 workflow 后续不再引用该条目
- **THEN** 系统 MUST 释放该缓存条目以回收内存

### Requirement: cache pool refcount MUST be derived from Workflow IR when available
当 workflow 具备 Workflow IR/DAG 信息时,系统 MUST 基于 IR 的静态依赖关系推导"哪个 node 会消费哪个缓存条目",以支持 DAG-based refcount 并尽早释放内存:
- 系统 MUST 在结构编译阶段推导 refcount 上界(consumer set),并在运行时随 node 完成递减
- 对于必须常驻到 workflow 结束的条目,系统 MUST 提供 pin 机制覆盖 refcount 行为

#### Scenario: DAG-based refcount releases early
- **GIVEN** cache entry 仅会被 node A/B/C 消费,且 C 为最后一个消费者
- **WHEN** node C 完成
- **THEN** 系统 MUST 将该 entry 的 refcount 变为 0 并释放(或进入可淘汰状态),而不是默认常驻到 workflow 结束


### Requirement: cache pool enforces budgets with a clear policy
系统 MUST 支持对 cache pool 设置预算(SSOT: `max_entries`),并在超限时采取明确策略:
- `fail_fast`: 新条目写入将导致超限时 fail-fast
- `evict_lru`: 淘汰 LRU 的 refcount=0 条目以腾挪空间；若无可淘汰条目,则 MUST fail-fast

#### Scenario: budget exceed triggers configured policy
- **GIVEN** cache pool 配置了预算与超限策略
- **WHEN** 新条目写入将导致超限
- **THEN** 系统 MUST 按该策略执行(报错或淘汰),且错误信息/事件 MUST 可用于排障

### Requirement: cache pool eviction MUST NOT evict in-flight (loading) entries
当 cache pool 条目处于 in-flight load(`loading=True`)时,系统 MUST NOT 将其作为 refcount/LRU 的淘汰候选;否则可能导致条目被逐出后成为"孤儿",从而触发重复加载与缓存不一致.

为避免"准备加载"与 eviction 之间的竞态窗口,系统 MUST 满足:

- 对任何 `get_or_load()` 调用,只要判定该次为 miss(`entry.value is None`)且将进入 load 流程,系统 MUST 在释放全局锁之前将该 entry 标记为 `loading=True`
- 该规则 MUST 覆盖"已有 entry 但 value 为空"的重试路径(例如前一次 `load_fn()` 抛异常后再次重试)
- `loading` MUST 在 load 完成(成功写入 value 或异常退出)后被恢复为 `False`

#### Scenario: refcount eviction skips loading entries
- **GIVEN** 某个 signature 的缓存条目处于 `loading=True`
- **WHEN** workflow node done 触发 refcount=0 的逐出逻辑
- **THEN** 逐出逻辑 MUST 跳过该条目
- **AND** 后续请求 MUST 复用该次 in-flight load 的结果(不得重复加载)

#### Scenario: budget eviction skips loading entries during retry miss window
- **GIVEN** 某 signature 的缓存条目曾因 `load_fn()` 异常而处于 `value=None`
- **AND** 另一线程对该 signature 发起重试 `get_or_load()` 并进入"准备加载"窗口
- **WHEN** 并发触发 over-budget LRU eviction 扫描
- **THEN** eviction MUST 将该条目视为 in-flight 并跳过(不得逐出)
- **AND** 重试 load 成功后,该条目 MUST 仍保留在 cache pool 中以供后续 hit 复用


### Requirement: `WorkflowCachePool.close` MUST synchronize with in-flight loads
`WorkflowCachePool.close()` MUST 在逐出或销毁条目之前，等待当前处于 `loading=True` 的条目完成加载（成功或失败），以避免关闭路径与 `load_fn` 并发导致的孤儿条目、重复加载或关闭后仍运行的后台加载。

- 等待逻辑 MUST 在获取 `entry.lock` 时与 `get_or_load` 的锁顺序一致：不得在持有全局 `self._lock` 的同时获取 `entry.lock`（与现有 `get_or_load` 约定一致），以避免死锁。
- 等待 MAY 带超时；若采用超时，行为 MUST 可诊断（例如明确错误或日志），且测试 MUST 覆盖正常完成路径。

#### Scenario: close waits for slow load
- **GIVEN** 某缓存条目的 `load_fn` 被 `threading.Event` 人为延长执行时间
- **WHEN** 另一线程在加载进行中调用 `close()`
- **THEN** `close()` MUST 等待该加载完成（在无限等待或文档化超时语义下）后再完成清理
- **AND** 不得留下对已逐出条目的写入或同一 key 的重复加载

### Requirement: LRU / refcount eviction MUST skip loading entries
`_evict_entry` 及由预算/refcount 触发的淘汰路径 MUST 跳过 `entry.loading` 为真的条目；该行为 MUST 与关闭路径协同，保证不会在加载持有 `entry.lock` 期间从 `_entries` 移除该条目。

#### Scenario: eviction does not orphan a loading entry
- **GIVEN** 某 signature 的条目处于 in-flight load（`loading=True`）
- **WHEN** 并发触发 LRU 或 refcount 驱动的逐出
- **THEN** 逐出逻辑 MUST NOT 将该条目从池中移除以致加载结果写入孤儿对象
- **AND** 加载完成后状态 MUST 与池内元数据一致

### Requirement: Concurrent safety MUST be covered by tests
系统 MUST 在 `tests/workflow/test_workflow_cache_pool.py`（或等价模块）中提供并发回归用例，至少覆盖：
- 加载进行中调用 `close()` 时，关闭与加载的交互符合上述要求。
- eviction 与对同一 key 的并发 `get_or_load` 不产生重复加载或缓存不一致。

#### Scenario: regression tests protect close vs load race
- **WHEN** 运行默认非 bench 测试套件中的 workflow cache pool 并发用例
- **THEN** 用例 MUST 通过并锁定上述安全语义

### Requirement: Optional `_closing` flag MUST not weaken documented API semantics
若实现引入 `_closing`（或等价）标志以使 `close()` 之后的新 `get_or_load` 快速失败，该行为 MUST 与现有对外 API 文档及错误语义一致，且 MUST 具备测试覆盖。

#### Scenario: new loads after close are rejected consistently
- **GIVEN** `close()` 已设置关闭状态（若采用 `_closing`）
- **WHEN** 调用方在关闭后尝试 `get_or_load`
- **THEN** 系统 MUST 以满足文档的方式失败（例如明确异常类型/消息），而不得静默返回陈旧或部分初始化的条目


### Requirement: cache pool MUST be observable via workflow-level events
系统 MUST 为 cache pool 的关键生命周期动作提供可观测事件/钩子点,以便 hooks/observers/scalim-viz 能解释"复用/释放/淘汰"导致的行为变化:
- 系统 MUST 发出以下事件类型:
  - `workflow_cache_acquire`
  - `workflow_cache_release`
  - `workflow_cache_evict`
- 事件 MUST 复用 workflow 归因字段(例如 `workflow_exec_id` / `workflow_node_id`)

#### Scenario: cache events are joinable back to workflow nodes
- **GIVEN** workflow node A acquire 一个 preload_forever cache entry
- **WHEN** observer 订阅 workflow-level 事件流
- **THEN** observer MUST 能观测到该 acquire 事件,且其 `workflow_node_id` MUST 等于 `"A"`
