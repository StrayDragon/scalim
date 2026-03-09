## MODIFIED Requirements

### Requirement: steps 结构与 relation 解析/推断规则
系统 SHALL 将关系定义为有序 `steps` 列表并按声明顺序执行;每个 step 包含 `from`/`to`(source.field 或同源列表)以及可选 `lookup_cast`,相邻 steps 必须链式相连.
字段通过 `relation` 提供 steps 对象(允许 YAML alias 复用),不支持 relation_id 字符串引用.
若 `relation` 缺省且字段 source 不是 main_source,系统仅在唯一路径存在时自动推断;无路径或多路径时校验失败.
`relation` steps 必须以 main_source 为起点、以字段 source 为终点,并保持 left join 语义(未命中保持 None).
系统 MUST 将 steps 中的依赖字段用于 ref loader 排序信号构建,以驱动 `ref_loader_sequence` 的依赖排序.

ref loader 的入参与绑定模式 MUST 通过目标 source 的 `params` 模板表达,而不是通过 step 级 `to_bind`.

#### Scenario: 多字段 step
- **WHEN** `from` 与 `to` 为等长同源列表
- **THEN** 系统应生成多字段 lookup,长度不一致应报错

#### Scenario: 路径歧义
- **WHEN** 未提供 `relation` 且存在多条有效路径
- **THEN** 校验失败并要求显式 `relation`

#### Scenario: relation_id 字符串被拒绝
- **WHEN** `relation` 使用字符串引用
- **THEN** 校验失败并提示仅支持 steps 对象

#### Scenario: 关联缺失
- **WHEN** 主源存在记录但关联源无匹配键
- **THEN** 关联字段结果应为 None 且主记录不被丢弃

#### Scenario: steps 驱动 loader 顺序
- **WHEN** steps 中后续字段依赖前序 ref loader 字段
- **THEN** 计划构建阶段必须将该依赖反映到 `ref_loader_sequence` 排序

### Requirement: 批次内 LoadRef 复用与分片语义
系统 MUST 在同一批次内对 relation signature 完全一致的 LoadRef 字段进行 group 合并并一次执行;signature 由 steps 中的 to_source/from_fields/to_key/lookup_cast/binding 组成.
系统 MUST 基于 group 内字段构建 lookup_keys 并集并写回所有字段;若 relation 不一致则不得合并.
系统 MUST 复用同 relation/row_id/from_field 的 lookup key 归一化结果;不同 relation 不复用,且诊断事件仅在首次归一化时触发.
rows 模式默认复用,若目标 source 的 `params` 模板中使用 `$rows: {cache_mode: none}`,系统 MUST 显式禁用该 relation 的批次内复用;复用使用首次调用的 batch_rows 快照.
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

## ADDED Requirements

### Requirement: ref loader params are expressed by target-source params templates
系统 SHALL 通过目标 source 的 `params` 模板内联指令(`$keys/$rows`)表达 ref loader 的入参与绑定模式,并用于 relation steps 的 `LoadRef` 调用.

#### Scenario: relation ref loader 通过 `$keys` 注入 lookup keys
- **GIVEN** relation steps 从 main_source 关联到 `sources.order_evaluations`
- **WHEN** `sources.order_evaluations.params` 使用 `$keys` 指令节点注入 lookup keys
- **THEN** 执行 `LoadRef` 时 MUST 将该步骤的 lookup keys 注入到模板对应位置并透传给 loader

#### Scenario: relation step without bind/to_bind remains valid
- **GIVEN** relation steps 指向一个非 preload source
- **AND** 目标 source 仅声明 `params` 模板(无 `bind/to_bind`)
- **THEN** relation 校验 MUST 通过
- **AND** `LoadRef` 时 MUST 按模板透传 loader kwargs

### Requirement: `$rows` preserves rows barrier semantics for relations
系统 MUST 将 `$rows` 指令视为 rows 模式绑定,并保留 rows barrier 语义(例如 adaptive 下该层串行)以及 `cache_mode` 语义.

#### Scenario: `$rows` 触发 rows barrier
- **WHEN** 某个 relation 目标 source 的 params 模板中出现 `$rows`
- **THEN** 该 relation 对应的 `LoadRef` 执行 MUST 按 rows barrier 语义串行运行(不得作为可并行 keys 任务执行)

### Requirement: preload_forever sources reject `$keys/$rows` directives
系统 MUST 禁止在 `cache_mode: preload_forever` 的 source 的 preload 调用路径中使用 `$keys/$rows` 指令节点(因为 preload 不具备 ref 上下文).

#### Scenario: preload_forever params 模板包含 `$keys` 被拒绝
- **WHEN** `sources.customers.cache_mode=preload_forever`
- **AND** `sources.customers.params` 中出现 `$keys` 或 `$rows`
- **THEN** 编译或校验 MUST 失败并报告配置路径

## REMOVED Requirements

### Requirement: bind/to_bind 结构与校验
**Reason**: 该 requirement 将 step 级 `to_bind` 与 source 级 `bind` 作为稳定 relation 入参 surface,与本 change 已决定的 `params` 模板方案相冲突.

**Migration**: 将 `to_bind.use_keys` / `to_bind.use_rows` 与 `sources.*.bind` 迁移为目标 source 的 `params` 模板,并用 `$keys` / `$rows` 指令表达动态上下文.
