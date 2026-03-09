## MODIFIED Requirements

### Requirement: 预加载缓存模式
系统 SHALL 支持 source `cache_mode=preload_forever`,并在执行前预加载该数据源结果.
系统 MUST 将 `source.cache_mode` 约束为显式枚举(当前仅允许 `none|preload_forever`),并在语义校验阶段拒绝未知值(避免拼写错误导致静默降级).

预加载调用 MUST 与常规 loader 调用保持一致的参数语义:
- 若 `sources.<id>.params` 非空,预加载时 MUST 以 `loader(**sources.<id>.params)` 形式调用,且 `sources.<id>.params` 中的 `$runtime.*` 必须先完成解析.
- 若 `sources.<id>.params` 为空,预加载时 MAY 使用零参调用以减少影响面.
- preload 与 ref loader MUST 共用同一份编译后的 params template representation,避免双轨 params 逻辑

#### Scenario: 预加载缓存数据源(透传 params)
- **WHEN** source 配置 `cache_mode=preload_forever`
- **AND** source 配置包含 `params={"params": {"group_by": "user_id"}}`
- **THEN** pipeline 启动前应调用 loader 并将结果缓存到 runtime.preloaded_cache
- **AND** loader 调用 MUST 透传 `params={"group_by": "user_id"}` 的 kwargs

#### Scenario: cache_mode 拼写错误被拒绝
- **WHEN** source 配置 `cache_mode=prelaod_forever`(拼写错误)
- **THEN** 语义校验必须失败并报告 `sources.<id>.cache_mode` 的错误
