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
- `src/IMPL_ROOT/execution/executor/operators/load_ref/loader.py` (cache hit path)
## Requirements
### Requirement: 预加载缓存模式
系统 SHALL 支持 source cache_mode=preload_forever,并在执行前预加载该数据源结果.
系统 MUST 将 `source.cache_mode` 约束为显式枚举(当前仅允许 `none|preload_forever`),并在语义校验阶段拒绝未知值(避免拼写错误导致静默降级).

预加载调用 MUST 与常规 loader 调用保持一致的参数语义:
- 若 `sources.<id>.params` 非空,预加载时 MUST 以 `loader(**sources.<id>.params)` 形式调用,且 `sources.<id>.params` 中的 `$runtime.*` 必须先完成解析.
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

## Notes
- 当前仅支持 preload_forever;缓存生命周期限定在单次 pipeline 运行中.
