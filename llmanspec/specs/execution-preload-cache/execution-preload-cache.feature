# language: zh-CN
# capability: execution-preload-cache
# purpose: 定义 `PreloadCache` 的完整行为契约：并发安全性、in-flight 去重、signature 冲突防护、诊断能力，以及并发场景下的幂等性期望。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: execution-preload-cache

  @req:r42 @human
  场景: PreloadCache waiter path MUST read inflight and fallback state under the per-sou
    - After an in-flight waiter's `Event` becomes done, the implementation MUST NOT read `inflight.error`, `inflight.value`, or decide fallback from `_data` outside the per-source lock. All such reads MUST occur in the same critical section pattern as existing `_data` access so that free-threaded runtimes cannot observe torn or inconsistent inflight fields.

  @req:r286 @human
  场景: preload cache hit path MUST be thread-safe under concurrent writers
    - 当同一个 `PreloadCache` 实例被多个线程共享时，系统 MUST 保证 `get_or_load(source_id, ...)` 的 cache hit 读路径在存在并发写入时仍然线程安全： - 系统 MUST 不以"无锁 membership check + 无锁 index read"的方式访问 `_data[source_id]` - 系统 MUST 使用与写路径一致的 per-source lock 来保护 "是否命中缓存" 与 "读取缓存值" 的临界区 - 系统 MUST NOT 因并发 dict 变更而在 hit 路径抛出 `KeyError`（或等价的 dict-mutation 竞态异常）

  @req:r410 @human
  场景: PreloadCache mapping introspection MUST be safe under concurrent mutation
    - `__iter__`, `__len__`, and `__contains__` on `PreloadCache` MUST operate on `_data` only while holding the existing global lock used for lock-table coordination (`_global_lock`). Iteration MUST use a snapshot of keys (or equivalent) so that concurrent `get_or_load` / writes do not cause dict-mutation errors or skipped elements during iteration.

  @req:r505 @human
  场景: PreloadCache MUST document its thread-safety contract
    - The class-level documentation MUST state which operations are synchronized, which lock protects `_data` vs lock-table vs inflight coordination, and that the implementation targets correctness under free-threaded Python as well as GIL-backed CPython.

  @req:r582 @human
  场景: PreloadCache concurrency MUST be covered by tests
    - The test suite MUST include multi-threaded coverage that exercises concurrent `get_or_load` together with concurrent iteration (`__iter__` / `len` / membership) on the same instance, in addition to existing behavior tests.

  @req:r641 @human
  场景: preload cache MUST dedupe inflight loads without holding locks during load_fn
    - 当多个线程并发请求同一 `source_id` 的 preload 值时，系统 MUST： - 对同一 `source_id` 的真实 `load_fn()` 执行次数上界为 1（inflight 去重） - 在执行 `load_fn()` 时 MUST 不持有保护缓存状态的互斥锁（避免外部回调在锁内执行） - 等待方 MUST 在 inflight 完成后获得一致的结果或一致的异常

  @req:r686 @human
  场景: signature mismatch MUST be detectable when guardrail enabled
    - 系统 MUST 为 `PreloadCache` 提供可选 guardrail 开关（默认关闭）,并在开启时检测同一 `source_id` 的 signature 冲突: - 系统 MUST 支持至少两种策略: `error|warn` - 当检测到同一 `source_id` 的 signature 不一致时: - `error`: MUST fail-fast - `warn`: MUST 产生强告警,且继续执行 - 诊断信息 MUST 可用于定位与迁移（至少包含 `source_id`、两次 signature digest、以及差异字段摘要或迁移提示）

  @req:r725 @human
  场景: default behavior MUST remain unchanged when guardrail disabled
    - 当 guardrail 关闭时,系统 MUST 保持既有语义（按 `source_id` key 做 per-key `in-flight` 去重与结果复用）,不得因 guardrail 的引入改变默认行为或引入新的数据竞态/死锁。

  @req:r757 @human
  场景: inflight wait diagnostics MUST be opt-in and include stable fields
    - 系统 MUST 提供 inflight 等待诊断能力，且默认关闭；仅在显式开启后生效。 在诊断模式开启时，当等待 inflight 超过阈值，系统 MUST 输出诊断信号，并包含稳定字段（至少包含 `source_id` 与 `wait_s`）。 诊断信号 SHOULD 遵循框架日志约定： - 前缀：`[scalim] preload-cache:` - 字段：稳定 `k=v`（至少 `source_id=<...> wait_s=<...>`），便于 grep/监控聚合

  @req:r138 @human
  场景: concurrency scenarios MUST be explicit and reproducible
    - 系统 MUST 明确并提供可复现的说明，至少覆盖： - 多线程并发多个 `ScalimEngine.run()` 且共享同一个 `preloaded_cache`（当 `preloaded_cache` 提供 `get_or_load` 时，应按 key 做 in-flight 去重） - workflow 多节点并发请求同一 `WorkflowCachePool` signature（同一 signature 同一时刻最多一个实际 `load_fn` 运行） 系统 MUST 明确默认语义仅为 **in-flight 去重**，不承诺跨进程去重。

  @req:r161 @human
  场景: loader idempotency expectations MUST be explicit
    - 当系统允许出现"同一逻辑数据源在并发场景下被重复触发 load"的可能性时（例如多 engine 共享 `PreloadCache`、workflow 多 node 并发请求），系统 MUST 明确并文档化 loader 的幂等性期望与风险边界： - 文档 MUST 明确说明：loader 实现 SHOULD 尽量满足幂等性（重复调用应产生等价结果或在可接受范围内一致） - 文档 MUST 明确说明：不应依赖"永不并发/永不重复调用"的隐式假设来保证正确性 - 若 loader 不可幂等（例如包含外部副作用），文档 MUST 明确提示风险，并建议调用方避免跨不同配置/不同 signature 复用同一 `PreloadCache`，或在后续启用更强 guardrail（若提供）

  @req:r45 @human
  场景: 预加载缓存模式
    - 系统 SHALL 支持 source `cache_mode=preload_forever`,并在执行前预加载该数据源结果。系统 MUST 将 `source.cache_mode` 约束为显式枚举(当前仅允许 `none|preload_forever`),并在语义校验阶段拒绝未知值。 预加载调用 MUST 与常规 loader 调用保持一致的参数语义: - 若 `sources.<id>.params` 非空,预加载时 MUST 以 `loader(**sources.<id>.params)` 形式调用,且 `sources.<id>.params` 中的 `{$runtime: <name>}` 必须先完成解析 - 若 `sources.<id>.params` 为空,预加载时 MAY 使用零参调用以减少影响面 - preload 与 ref loader MUST 共用同一份编译后的 params template representation,避免双轨 params 逻辑

  @req:r289 @human
  场景: 关联加载优先命中缓存
    - 系统 SHALL 在关联查找时优先使用预加载缓存结果,避免重复调用 loader。

  @req:r413 @human
  场景: 计划元数据记录缓存源
    - 系统 SHALL 在执行计划元数据中记录缓存数据源列表。

  @req:r508 @human
  场景: preload cache 存储 normalized 结果
    - 系统 MUST 在 `cache_mode=preload_forever` 的 source 上先应用 `normalize`,再把结果写入 preload cache,并确保 cache hit 与非 cache path 观察到同样的结果形状。
  @req:r42 @human
  场景: waiter-observes-completed-load-under-lock
    - 必须成立：当 a thread waits on `inflight.done` in `get_or_load` and the wait returns；那么 the implementation MUST acquire the per-source lock before reading `inflight.error` / `inflight.value` or returning a value from `_data` for that source
    当 a thread waits on `inflight.done` in `get_or_load` and the wait returns
    那么 the implementation MUST acquire the per-source lock before reading `inflight.error` / `inflight.value` or returning a value from `_data` for that source
  @req:r286 @human
  场景: cache-hit-does-not-raise-keyerror-under-concurrent-updates
    - 必须成立：假如 两个线程共享同一个 `PreloadCache`；当 线程 B 并发反复调用 `get_or_load(source_id, load_fn)` 且多次命中缓存；那么 线程 B 的调用 MUST NOT 因 hit 快路径的竞态而抛出 `KeyError`
    假如 两个线程共享同一个 `PreloadCache`
    当 线程 B 并发反复调用 `get_or_load(source_id, load_fn)` 且多次命中缓存
    那么 线程 B 的调用 MUST NOT 因 hit 快路径的竞态而抛出 `KeyError`
  @req:r410 @human
  场景: concurrent-iteration-and-load
    - 必须成立：当 one thread iterates or calls `len` / `__contains__` while other threads call `get_or_load` or mutate the cache；那么 those introspection operations MUST NOT raise exceptions due to concurrent dict modification
    当 one thread iterates or calls `len` / `__contains__` while other threads call `get_or_load` or mutate the cache
    那么 those introspection operations MUST NOT raise exceptions due to concurrent dict modification
  @req:r505 @human
  场景: maintainers-understand-boundaries
    - 必须成立：当 a developer reads the `PreloadCache` docstring；那么 they MUST be able to see explicit thread-safety boundaries and assumptions without reading implementation details alone
    当 a developer reads the `PreloadCache` docstring
    那么 they MUST be able to see explicit thread-safety boundaries and assumptions without reading implementation details alone
  @req:r582 @human
  场景: regression-guard-for-thread-safety-fixes
    - 必须成立：当 CI runs the workflow/cache-related test gate；那么 tests MUST exercise concurrent waiters and concurrent introspection without flaky failures
    当 CI runs the workflow/cache-related test gate
    那么 tests MUST exercise concurrent waiters and concurrent introspection without flaky failures
  @req:r641 @human
  场景: concurrent-callers-observe-one-load-and-the-same-cached-resu
    - 必须成立：当 两个线程同时调用 `get_or_load("src", load_fn)`；那么 `load_fn` MUST 仅被调用一次
    当 两个线程同时调用 `get_or_load("src", load_fn)`
    那么 `load_fn` MUST 仅被调用一次
  @req:r686 @human
  场景: signature-mismatch-fails-fast-in-error-mode
    - 必须成立：假如 共享同一个 `PreloadCache`；当 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）；那么 系统 MUST fail-fast
    假如 共享同一个 `PreloadCache`
    当 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
    那么 系统 MUST fail-fast

  @req:r686 @human
  场景: signature-mismatch-warns-in-warn-mode
    - 必须成立：假如 共享同一个 `PreloadCache`；当 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）；那么 系统 MUST 产生强告警且继续执行
    假如 共享同一个 `PreloadCache`
    当 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
    那么 系统 MUST 产生强告警且继续执行
  @req:r725 @human
  场景: guardrail-disabled-keeps-legacy-semantics
    - 必须成立：当 guardrail 未开启；那么 `PreloadCache.get_or_load(source_id, ...)` 的 key MUST 仍为 `source_id`
    当 guardrail 未开启
    那么 `PreloadCache.get_or_load(source_id, ...)` 的 key MUST 仍为 `source_id`
  @req:r757 @human
  场景: long-inflight-wait-emits-warning-only-when-diagnostics-enabl
    - 必须成立：假如 preload cache inflight wait diagnostics 已显式开启；当 某线程等待 inflight 的时间超过阈值；那么 系统 MUST 输出一次 warning 诊断信号
    假如 preload cache inflight wait diagnostics 已显式开启
    当 某线程等待 inflight 的时间超过阈值
    那么 系统 MUST 输出一次 warning 诊断信号
  @req:r138 @human
  场景: two-concurrent-callers-trigger-at-most-one-in-flight-load-pe
    - 必须成立：假如 两个并发执行单元（线程或 workflow node）请求同一缓存 key（`source_id` 或 signature）；当 该 key 当前为 miss；那么 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
    假如 两个并发执行单元（线程或 workflow node）请求同一缓存 key（`source_id` 或 signature）
    当 该 key 当前为 miss
    那么 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
  @req:r161 @human
  场景: preload-forever-docs-mention-idempotency-expectations
    - 必须成立：当 系统文档描述 `preload_forever` / `PreloadCache` 的并发边界与 in-flight 去重语义；那么 文档 MUST 同时包含关于 loader 幂等性（SHOULD）与非幂等风险的明确说明
    当 系统文档描述 `preload_forever` / `PreloadCache` 的并发边界与 in-flight 去重语义
    那么 文档 MUST 同时包含关于 loader 幂等性（SHOULD）与非幂等风险的明确说明
  @req:r45 @human
  场景: 预加载缓存数据源
    - 必须成立：当 source 配置 `cache_mode=preload_forever`；那么 pipeline 启动前应调用 loader 并将结果缓存到 runtime.preloaded_cache
    当 source 配置 `cache_mode=preload_forever`
    那么 pipeline 启动前应调用 loader 并将结果缓存到 runtime.preloaded_cache

  @req:r45 @human
  场景: 预加载缓存透传参数
    - 必须成立：当 source 配置 `cache_mode=preload_forever` 且包含 `params`；那么 pipeline 启动前应调用 loader 并透传 params 的 kwargs
    当 source 配置 `cache_mode=preload_forever` 且包含 `params`
    那么 pipeline 启动前应调用 loader 并透传 params 的 kwargs

  @req:r45 @human
  场景: cache-mode-拼写错误被拒绝
    - 必须成立：当 source 配置 `cache_mode=prelaod_forever`(拼写错误)；那么 语义校验必须失败并报告 `sources.<id>.cache_mode` 的错误
    当 source 配置 `cache_mode=prelaod_forever`(拼写错误)
    那么 语义校验必须失败并报告 `sources.<id>.cache_mode` 的错误
  @req:r289 @human
  场景: 关联命中缓存
    - 必须成立：当 关联目标源已被 preload_forever 缓存；那么 关联加载应直接从缓存读取结果
    当 关联目标源已被 preload_forever 缓存
    那么 关联加载应直接从缓存读取结果
  @req:r413 @human
  场景: 记录缓存源
    - 必须成立：当 构建执行计划；那么 metadata.cached_sources 应包含 preload_forever 数据源名称
    当 构建执行计划
    那么 metadata.cached_sources 应包含 preload_forever 数据源名称
  @req:r508 @human
  场景: preload-缓存写入-normalized-mapping
    - 必须成立：当 source 同时声明 cache_mode=preload_forever 与 normalize: index_by_key；那么 pipeline preload 阶段 MUST 将 index_by_key 归一化后的 mapping 写入 runtime.preloaded_cache
    当 source 同时声明 cache_mode=preload_forever 与 normalize: index_by_key
    那么 pipeline preload 阶段 MUST 将 index_by_key 归一化后的 mapping 写入 runtime.preloaded_cache

  @req:r508 @human
  场景: cache-hit-路径不重复看到-raw-list
    - 必须成立：当 后续关联加载命中 preload cache；那么 关联读取 MUST 直接消费 normalized mapping
    当 后续关联加载命中 preload cache
    那么 关联读取 MUST 直接消费 normalized mapping
