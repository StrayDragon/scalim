## MODIFIED Requirements

### Requirement: preload cache 存储 normalized 结果
系统 MUST 在 `cache_mode=preload_forever` 的 source 上先应用 `normalize`,再把结果写入 preload cache,并确保 cache hit 与非 cache path 观察到同样的结果形状。

#### Scenario: preload 缓存写入 normalized mapping
- **WHEN** source 同时声明 `cache_mode=preload_forever` 与 `normalize: {index_by_key: {}}`
- **THEN** pipeline preload 阶段 MUST 将 `index_by_key` 归一化后的 mapping 写入 `runtime.preloaded_cache`

#### Scenario: cache hit 路径不重复看到 raw list
- **WHEN** 后续关联加载命中 preload cache
- **THEN** 关联读取 MUST 直接消费 normalized mapping
- **AND** MUST NOT 再暴露原始 `list[row]` 形状给字段读取逻辑
