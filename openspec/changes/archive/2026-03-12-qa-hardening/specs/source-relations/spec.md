## MODIFIED Requirements

### Requirement: 批次内 LoadRef 复用与分片语义
系统 MUST 在同一批次内对 relation signature 完全一致的 LoadRef 字段进行 group 合并并一次执行;signature 由 steps 中的 to_source/from_fields/to_key/lookup_cast/binding 组成.
系统 MUST 基于 group 内字段构建 lookup_keys 并集并写回所有字段;若 relation 不一致则不得合并.
系统 MUST 复用同 relation/row_id/from_field 的 lookup key 归一化结果;不同 relation 不复用,且诊断事件仅在首次归一化时触发.
rows 模式默认复用,若目标 source 的 `params` 模板中使用 `$rows: {cache_mode: none}`,系统 MUST 显式禁用该 relation 的批次内复用.
当 rows 模式复用启用时,系统 MUST NOT 在长生命周期缓存中保留完整 `batch_rows` 列表;如需用于观测,系统 MAY 仅保留有界采样或在 cache hit 观测中省略 `batch_rows`.
keys 模式支持 `lookup_chunk_size` 分片加载并合并结果;分片语义与一次性加载一致.

#### Scenario: 同 relation 多字段只执行一次
- **GIVEN** fields `f1/f2/f3` 指向同一 `source`,且 relation signature 完全一致
- **WHEN** 批次执行 LoadRef
- **THEN** 该 group 在该批次仅触发一次逻辑加载
- **AND** loader_context.field_keys 应为 `[f1, f2, f3]`

#### Scenario: `$rows.cache_mode=none` 禁用复用
- **WHEN** relation 目标 source 的 `params` 模板使用 `$rows: {cache_mode: none}`
- **THEN** 系统不得对该 relation 做 group 合并

#### Scenario: lookup_chunk_size 分片加载
- **WHEN** lookup_keys 数量为 25 且 lookup_chunk_size=10
- **THEN** loader 应被调用 3 次且合并结果一致
