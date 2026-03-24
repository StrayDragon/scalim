# source-cache Specification

**状态: ✅ 已实现**
## Purpose
支持 cache_mode=preload_forever 的数据源在 pipeline 启动前预加载,结果写入 ExecutionRuntime.preloaded_cache 并在关联加载时复用;计划元数据记录已缓存的数据源.

## Context
**FR003: 小数据集全局缓存优化**

对于高频且内存占用小的映射表(如国家地区表、枚举常量映射表),希望作为全局一次性导入使用,以加速获值速度.

这种数据源在执行前全局初始化,执行计划感知其为特殊数据源,但对外表现与普通数据源一致.

## Related Code (as implemented)
- `src/IMPL_ROOT/planning/builder.py` (`ExecutionPlan.preload_sources`)
- `src/IMPL_ROOT/execution/pipeline/base/pipeline.py` (`Pipeline._preload_cached_sources`)
- `src/IMPL_ROOT/execution/preload_cache.py` (`PreloadCache.get_or_load`)
- `src/IMPL_ROOT/execution/executor/operators/load_ref/loader.py` (cache hit path)
## Requirements
### Requirement: 预加载缓存模式
系统 SHALL 支持 source cache_mode=preload_forever,并在执行前预加载该数据源结果.
系统 MUST 将 `source.cache_mode` 约束为显式枚举(当前仅允许 `none|preload_forever`),并在语义校验阶段拒绝未知值(避免拼写错误导致静默降级).

预加载调用 MUST 与常规 loader 调用保持一致的参数语义:
- 若 `sources.<id>.params` 非空,预加载时 MUST 以 `loader(**sources.<id>.params)` 形式调用,且 `sources.<id>.params` 中的 `{$runtime: <name>}` 必须先完成解析.
- 若 `sources.<id>.params` 为空,预加载时 MAY 使用零参调用以减少影响面.
- preload 与 ref loader MUST 共用同一份编译后的 params template representation,避免双轨 params 逻辑

#### Scenario: 预加载缓存数据源
- **WHEN** source 配置 cache_mode=preload_forever
- **THEN** pipeline 启动前应调用 loader 并将结果缓存到 runtime.preloaded_cache

#### Scenario: 预加载缓存数据源(透传 params)
- **WHEN** source 配置 `cache_mode=preload_forever`
- **AND** source 配置包含 `params={"params": {"group_by": "user_id"}}`
- **THEN** pipeline 启动前应调用 loader 并将结果缓存到 runtime.preloaded_cache
- **AND** loader 调用 MUST 透传 `params={"group_by": "user_id"}` 的 kwargs

#### Scenario: cache_mode 拼写错误被拒绝
- **WHEN** source 配置 cache_mode=prelaod_forever(拼写错误)
- **THEN** 语义校验必须失败并报告 `sources.<id>.cache_mode` 的错误

### Requirement: 关联加载优先命中缓存
系统 SHALL 在关联查找时优先使用预加载缓存结果,避免重复调用 loader.

#### Scenario: 关联命中缓存
- **WHEN** 关联目标源已被 preload_forever 缓存
- **THEN** 关联加载应直接从缓存读取结果

### Requirement: 计划元数据记录缓存源
系统 SHALL 在执行计划元数据中记录缓存数据源列表.

#### Scenario: 记录缓存源
- **WHEN** 构建执行计划
- **THEN** metadata.cached_sources 应包含 preload_forever 数据源名称

### Requirement: preload cache stores normalized source results
系统 MUST 在 `cache_mode=preload_forever` 的 source 上先应用 `normalize`,再把结果写入 preload cache,并确保 cache hit 与非 cache path 观察到同样的结果形状。

#### Scenario: preload 缓存写入 normalized mapping
- **WHEN** source 同时声明 `cache_mode=preload_forever` 与 `normalize.kind=index_by_key`
- **THEN** pipeline preload 阶段 MUST 将 `index_by_key` 归一化后的 mapping 写入 `runtime.preloaded_cache`

#### Scenario: cache hit 路径不重复看到 raw list
- **WHEN** 后续关联加载命中 preload cache
- **THEN** 关联读取 MUST 直接消费 normalized mapping
- **AND** MUST NOT 再暴露原始 `list[row]` 形状给字段读取逻辑

### Requirement: `preloaded_cache` concurrency boundary and key space MUST be explicit
系统 MUST 明确 `ExecutionRuntime.preloaded_cache` 的 key 空间与并发边界（避免将其误解为“天然不会并发的全局缓存”）：

- `preloaded_cache` 为可注入容器,生命周期由调用方决定;系统默认仅承诺 per-key `in-flight` 去重与结果复用（不承诺跨进程/跨不同 signature 的全局去重）。
- 当多个并发执行单元共享同一个 `preloaded_cache`（例如多 `ScalimEngine.run()` 并发共享容器,或 workflow 多 node 并发共享容器）时,容器 MUST 是线程安全的（推荐使用 `PreloadCache`）；普通 `dict` 在并发下行为未定义。
- `PreloadCache.get_or_load(source_id, ...)` 的 key 为 `source_id`（不包含 loader/params/normalize signature）。跨不同 signature 复用同一 `source_id` 可能产生**错误复用**,其风险与责任边界 MUST 在文档中明确（调用方需避免此类复用或使用更强 guardrail）。

#### Scenario: concurrent callers dedupe at most one in-flight load per `source_id`
- **GIVEN** 两个线程并发对同一 `source_id` 调用 `PreloadCache.get_or_load(...)`
- **WHEN** 该 `source_id` 当前为 miss
- **THEN** 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
- **AND** 其余请求 MUST 等待并复用该次 load 的结果或异常
- Repro: `tests/test_preload_cache.py::test_preload_cache_get_or_load_returns_cached_value_inside_lock`

### Requirement: `PreloadCache` signature guardrail MUST be available (opt-in)
系统 MUST 为共享 `PreloadCache` 场景提供可选的 signature guardrail（默认关闭）,用于检测同一 `source_id` 被不同 signature 复用的风险,并在开发/测试阶段尽早暴露问题。

开启后系统 MUST:

- 支持至少两种策略: `error|warn`
- 当同一 `source_id` 的 signature digest 不一致时:
  - `error`: MUST fail-fast
  - `warn`: MUST 产生强告警,且继续执行
- 诊断信息 MUST 可用于定位与迁移（至少包含 `source_id`、两次 signature digest、以及迁移提示）

signature digest 的 SSOT MUST 与 `WorkflowCacheEntrySignature` 对齐（复用 canonicalization/digest 口径）,并至少覆盖:

- `loader_ref`
- 渲染后的 `params`（含 `$runtime` 解析结果）
- `normalize`
- `key`
- `lookup_cast`

#### Scenario: signature mismatch fails fast in `error` mode
- **GIVEN** 共享同一个 `PreloadCache` 且该 cache 已记录 `source_id="s1"` 的 signature digest 为 A
- **WHEN** 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
- **AND** 策略为 `error`
- **THEN** 系统 MUST fail-fast
- Repro: `tests/test_preload_cache.py::test_preload_cache_signature_guardrail_error_mode_fails_fast_on_mismatch`

#### Scenario: signature mismatch warns in `warn` mode
- **GIVEN** 共享同一个 `PreloadCache` 且该 cache 已记录 `source_id="s1"` 的 signature digest 为 A
- **WHEN** 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
- **AND** 策略为 `warn`
- **THEN** 系统 MUST 产生强告警且继续执行
- Repro: `tests/test_preload_cache.py::test_preload_cache_signature_guardrail_warn_mode_emits_warning_and_continues`

### Requirement: loader SHOULD be idempotent when concurrent / repeated loads are possible
当系统允许出现并发或重复触发 preload load 的现实路径时（例如多 engine 共享同一 `PreloadCache`,或 workflow 多 node 并发请求同一条目）,系统 MUST 明确 loader 的幂等性期望与风险边界：

- loader 实现 SHOULD 尽量满足幂等性（重复调用产生等价结果,或在可接受范围内一致）
- 系统 MUST 明确: 不应依赖“永不并发/永不重复调用”的隐式假设来保证正确性
- 若 loader 不可幂等（例如包含外部副作用）,系统 MUST 明确提示风险,并建议调用方避免跨不同配置/不同 signature 复用同一 `PreloadCache`（或在后续启用更强 guardrail 若提供）

#### Scenario: preload_forever docs mention idempotency expectations
- **WHEN** 系统文档描述 `preload_forever` / `PreloadCache` 的并发边界与 per-key `in-flight` 去重语义
- **THEN** 文档 MUST 同时包含关于 loader 幂等性（SHOULD）与非幂等风险的明确说明

## Notes
- 当前仅支持 preload_forever;默认语义仅承诺 per-key `in-flight` 去重.
- `preloaded_cache` 为可注入容器,可能被共享并跨多次运行复用;调用方需自行管理其生命周期与线程安全边界.
