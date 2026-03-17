## ADDED Requirements

### Requirement: workflow provides a cache pool with signature-based keys
系统 MUST 在一次 workflow 执行内提供 workflow-scope cache pool,用于承载可共享的缓存条目(例如 preload_forever 结果、未来的 dataset/index 工件等)。

cache pool MUST 将“可复现的 signature”纳入缓存 key,以避免复用错误数据;signature 至少应包含:
- 缓存条目 kind(例如 preload_forever / dataset_index)
- `source_id`(或 artifact id)
- loader 引用(或 artifact producer 节点信息)
- 渲染后的 params(含已解析的 `{$init_var: ...}`)
- normalize/lookup context 等会影响结果形状的关键字段

#### Scenario: same signature reuses cache entry
- **GIVEN** 两个 run 请求同一个缓存条目且其 signature 完全一致
- **WHEN** cache pool 已存在该条目
- **THEN** 系统 MUST 复用该缓存结果(不得重复加载/构造)

#### Scenario: different signature does not reuse cache entry
- **GIVEN** 两个 run 请求同一个 `source_id` 但 loader/params/normalize 不同导致 signature 不一致
- **WHEN** 两个请求先后发生
- **THEN** 系统 MUST NOT 复用错误的缓存结果

### Requirement: cache pool supports lifecycle management and auto-release
系统 SHALL 支持 cache pool 的生命周期管理,以减少 workflow 常驻内存:
- 系统 SHOULD 能基于 workflow DAG 推导缓存条目的引用集合,并维护引用计数
- 当引用计数归零时,系统 SHOULD 释放该缓存条目(或使其进入可淘汰状态)
- 系统 MUST 提供 pin/release_policy 等机制,以允许“常驻到 workflow 结束”的缓存条目

#### Scenario: cache entry is released after last consumer finishes
- **GIVEN** 某个缓存条目只会被 run A 与 run B 消费,且 run B 为该条目的最后一个消费者
- **WHEN** run B 完成且 workflow 后续不再引用该条目
- **THEN** 系统 SHOULD 释放该缓存条目以回收内存

### Requirement: cache pool enforces budgets with a clear policy
系统 SHALL 支持对 cache pool 设置预算(例如条目数/估算字节数),并在超限时采取明确策略:
- fail-fast(严格护栏),或
- 淘汰(例如 LRU;且不得淘汰仍被引用的条目)

#### Scenario: budget exceed triggers configured policy
- **GIVEN** cache pool 配置了预算与超限策略
- **WHEN** 新条目写入将导致超限
- **THEN** 系统 MUST 按该策略执行(报错或淘汰),且错误信息/事件 MUST 可用于排障
