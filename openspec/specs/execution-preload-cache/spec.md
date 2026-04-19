# preload-cache Specification

## Purpose
定义 `PreloadCache` 的完整行为契约：并发安全性、in-flight 去重、signature 冲突防护、诊断能力，以及并发场景下的幂等性期望。

## Requirements


### Requirement: PreloadCache waiter path MUST read inflight and fallback state under the per-source lock

After an in-flight waiter's `Event` becomes done, the implementation MUST NOT read `inflight.error`, `inflight.value`, or decide fallback from `_data` outside the per-source lock. All such reads MUST occur in the same critical section pattern as existing `_data` access so that free-threaded runtimes cannot observe torn or inconsistent inflight fields.

#### Scenario: Waiter observes completed load under lock
- **WHEN** a thread waits on `inflight.done` in `get_or_load` and the wait returns
- **THEN** the implementation MUST acquire the per-source lock before reading `inflight.error` / `inflight.value` or returning a value from `_data` for that source
- **AND** the returned value or raised exception MUST match the same ordering guarantees as the non-waiter code paths

### Requirement: preload cache hit path MUST be thread-safe under concurrent writers

当同一个 `PreloadCache` 实例被多个线程共享时，系统 MUST 保证 `get_or_load(source_id, ...)` 的 cache hit 读路径在存在并发写入时仍然线程安全：

- 系统 MUST 不以"无锁 membership check + 无锁 index read"的方式访问 `_data[source_id]`
- 系统 MUST 使用与写路径一致的 per-source lock 来保护 "是否命中缓存" 与 "读取缓存值" 的临界区
- 系统 MUST NOT 因并发 dict 变更而在 hit 路径抛出 `KeyError`（或等价的 dict-mutation 竞态异常）

#### Scenario: cache hit does not raise KeyError under concurrent updates
- **GIVEN** 两个线程共享同一个 `PreloadCache`
- **AND** 线程 A 会对同一 `source_id` 的缓存值执行更新/删除（例如 owner 写入 `_data[source_id] = value`，或通过 `__setitem__` / `__delitem__`）
- **WHEN** 线程 B 并发反复调用 `get_or_load(source_id, load_fn)` 且多次命中缓存
- **THEN** 线程 B 的调用 MUST NOT 因 hit 快路径的竞态而抛出 `KeyError`
- **AND** 命中缓存时返回值 MUST 为在同步临界区内观测到的缓存值（或在 miss 时按既有 in-flight 去重语义进入 load 路径）

### Requirement: PreloadCache mapping introspection MUST be safe under concurrent mutation

`__iter__`, `__len__`, and `__contains__` on `PreloadCache` MUST operate on `_data` only while holding the existing global lock used for lock-table coordination (`_global_lock`). Iteration MUST use a snapshot of keys (or equivalent) so that concurrent `get_or_load` / writes do not cause dict-mutation errors or skipped elements during iteration.

#### Scenario: Concurrent iteration and load
- **WHEN** one thread iterates or calls `len` / `__contains__` while other threads call `get_or_load` or mutate the cache
- **THEN** those introspection operations MUST NOT raise exceptions due to concurrent dict modification
- **AND** `__iter__` MUST yield a consistent snapshot of keys as of the time the snapshot was taken

### Requirement: PreloadCache MUST document its thread-safety contract

The class-level documentation MUST state which operations are synchronized, which lock protects `_data` vs lock-table vs inflight coordination, and that the implementation targets correctness under free-threaded Python as well as GIL-backed CPython.

#### Scenario: Maintainers understand boundaries
- **WHEN** a developer reads the `PreloadCache` docstring
- **THEN** they MUST be able to see explicit thread-safety boundaries and assumptions without reading implementation details alone

### Requirement: PreloadCache concurrency MUST be covered by tests

The test suite MUST include multi-threaded coverage that exercises concurrent `get_or_load` together with concurrent iteration (`__iter__` / `len` / membership) on the same instance, in addition to existing behavior tests.

#### Scenario: Regression guard for thread-safety fixes
- **WHEN** CI runs the workflow/cache-related test gate
- **THEN** tests MUST exercise concurrent waiters and concurrent introspection without flaky failures


### Requirement: preload cache MUST dedupe inflight loads without holding locks during load_fn

当多个线程并发请求同一 `source_id` 的 preload 值时，系统 MUST：

- 对同一 `source_id` 的真实 `load_fn()` 执行次数上界为 1（inflight 去重）
- 在执行 `load_fn()` 时 MUST 不持有保护缓存状态的互斥锁（避免外部回调在锁内执行）
- 等待方 MUST 在 inflight 完成后获得一致的结果或一致的异常

#### Scenario: concurrent callers observe one load and the same cached result
- **WHEN** 两个线程同时调用 `get_or_load("src", load_fn)`
- **AND** `load_fn` 返回 `{1: {"value": "x"}}`
- **THEN** `load_fn` MUST 仅被调用一次
- **AND** 两个线程 MUST 均返回相同的 mapping 结果


### Requirement: signature mismatch MUST be detectable when guardrail enabled

系统 MUST 为 `PreloadCache` 提供可选 guardrail 开关（默认关闭）,并在开启时检测同一 `source_id` 的 signature 冲突:

- 系统 MUST 支持至少两种策略: `error|warn`
- 当检测到同一 `source_id` 的 signature 不一致时:
  - `error`: MUST fail-fast
  - `warn`: MUST 产生强告警,且继续执行
- 诊断信息 MUST 可用于定位与迁移（至少包含 `source_id`、两次 signature digest、以及差异字段摘要或迁移提示）

#### Scenario: signature mismatch fails fast in `error` mode
- **GIVEN** 共享同一个 `PreloadCache`
- **AND** 该 `PreloadCache` 已缓存 `source_id="s1"` 的结果,其 signature digest 为 A
- **WHEN** 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
- **AND** guardrail 策略为 `error`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 包含 `source_id="s1"` 与 A/B 的差异诊断

#### Scenario: signature mismatch warns in `warn` mode
- **GIVEN** 共享同一个 `PreloadCache`
- **AND** 该 `PreloadCache` 已缓存 `source_id="s1"` 的结果,其 signature digest 为 A
- **WHEN** 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
- **AND** guardrail 策略为 `warn`
- **THEN** 系统 MUST 产生强告警且继续执行

### Requirement: default behavior MUST remain unchanged when guardrail disabled

当 guardrail 关闭时,系统 MUST 保持既有语义（按 `source_id` key 做 per-key `in-flight` 去重与结果复用）,不得因 guardrail 的引入改变默认行为或引入新的数据竞态/死锁。

#### Scenario: guardrail disabled keeps legacy semantics
- **WHEN** guardrail 未开启
- **THEN** `PreloadCache.get_or_load(source_id, ...)` 的 key MUST 仍为 `source_id`
- **AND** 同一 `source_id` 并发请求 MUST 仍只触发一次实际 `load_fn`


### Requirement: inflight wait diagnostics MUST be opt-in and include stable fields

系统 MUST 提供 inflight 等待诊断能力，且默认关闭；仅在显式开启后生效。

在诊断模式开启时，当等待 inflight 超过阈值，系统 MUST 输出诊断信号，并包含稳定字段（至少包含 `source_id` 与 `wait_s`）。

诊断信号 SHOULD 遵循框架日志约定：

- 前缀：`[scalim] preload-cache:`
- 字段：稳定 `k=v`（至少 `source_id=<...> wait_s=<...>`），便于 grep/监控聚合

#### Scenario: long inflight wait emits warning only when diagnostics enabled
- **GIVEN** preload cache inflight wait diagnostics 已显式开启
- **WHEN** 某线程等待 inflight 的时间超过阈值
- **THEN** 系统 MUST 输出一次 warning 诊断信号
- **AND** warning MUST 包含稳定字段 `source_id` 与 `wait_s`


### Requirement: concurrency scenarios MUST be explicit and reproducible

系统 MUST 明确并提供可复现的说明，至少覆盖：

- 多线程并发多个 `ScalimEngine.run()` 且共享同一个 `preloaded_cache`（当 `preloaded_cache` 提供 `get_or_load` 时，应按 key 做 in-flight 去重）
- workflow 多节点并发请求同一 `WorkflowCachePool` signature（同一 signature 同一时刻最多一个实际 `load_fn` 运行）

系统 MUST 明确默认语义仅为 **in-flight 去重**，不承诺跨进程去重。

#### Scenario: two concurrent callers trigger at most one in-flight load per key
- **GIVEN** 两个并发执行单元（线程或 workflow node）请求同一缓存 key（`source_id` 或 signature）
- **WHEN** 该 key 当前为 miss
- **THEN** 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
- **AND** 其余请求 MUST 等待并复用该次 load 的结果或异常

### Requirement: loader idempotency expectations MUST be explicit

当系统允许出现"同一逻辑数据源在并发场景下被重复触发 load"的可能性时（例如多 engine 共享 `PreloadCache`、workflow 多 node 并发请求），系统 MUST 明确并文档化 loader 的幂等性期望与风险边界：

- 文档 MUST 明确说明：loader 实现 SHOULD 尽量满足幂等性（重复调用应产生等价结果或在可接受范围内一致）
- 文档 MUST 明确说明：不应依赖"永不并发/永不重复调用"的隐式假设来保证正确性
- 若 loader 不可幂等（例如包含外部副作用），文档 MUST 明确提示风险，并建议调用方避免跨不同配置/不同 signature 复用同一 `PreloadCache`，或在后续启用更强 guardrail（若提供）

#### Scenario: preload_forever docs mention idempotency expectations
- **WHEN** 系统文档描述 `preload_forever` / `PreloadCache` 的并发边界与 in-flight 去重语义
- **THEN** 文档 MUST 同时包含关于 loader 幂等性（SHOULD）与非幂等风险的明确说明
