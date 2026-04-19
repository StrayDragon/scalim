# source-relations Specification

**状态: ✅ 已实现**
## Purpose
使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义.

## Context
**FR011: 数据源多种关联方式**

数据源之间需要支持单字段、多字段与多级链式关联,并能明确指定关联路径与键规范化逻辑.

**FR013: 多数据源外键类型不匹配导致无法关联**

关联键类型可能不同(如字符串 "123" vs 整数 123),需要在 lookup 前进行规范化以保证字典查找命中.

## Related Code (as implemented)
- `src/IMPL_ROOT/spec/ir/relations.py` (steps IR)
- `src/IMPL_ROOT/spec/ir/sources.py` (`KeyIr.cast`)
- `src/IMPL_ROOT/utils/converters.py` (`auto_normalize_key` + cast helpers)
- `src/IMPL_ROOT/execution/executor/operators/load_ref/loader.py` (lookup execution + chunking)
- `src/IMPL_ROOT/dsl/yaml_dsl/runtime/conversion.py` (YAML → relation IR compilation)
- `src/IMPL_ROOT/planning/loader_ordering/deps.py` / `src/IMPL_ROOT/planning/loader_ordering/sequences.py`
- `src/IMPL_ROOT/utils/relation_diagnostics.py`
## Requirements
### Requirement: steps 结构与 relation 解析/推断规则
系统 SHALL 将关系定义为有序 `steps` 列表并按声明顺序执行;每个 step 包含 `from`/`to`(source.field 或同源列表)以及可选 `lookup_cast`,相邻 steps 必须链式相连.
字段通过 `relation` 提供 steps 对象(允许 YAML alias 复用),不支持 relation_id 字符串引用.
若 `relation` 缺省且字段 source 不是 main_source,系统仅在唯一路径存在时自动推断;无路径或多路径时校验失败.
`relation` steps 必须以 main_source 为起点、以字段 source 为终点,并保持 left join 语义(未命中不丢弃主记录;字段值缺省为 None,但当字段声明了 relation miss default 时 MUST 写回该默认值).
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

#### Scenario: 关联缺失（无 default）
- **GIVEN** 主源存在记录但关联源无匹配键
- **AND** 该 ref 字段未声明 relation miss default
- **THEN** 关联字段结果应为 None 且主记录不被丢弃

#### Scenario: 关联缺失（有 default）
- **GIVEN** 主源存在记录但关联源无匹配键
- **AND** 该 ref 字段声明了 relation miss default
- **THEN** 系统 MUST 写回该默认值
- **AND** 主记录 MUST NOT 被丢弃

#### Scenario: steps 驱动 loader 顺序
- **WHEN** steps 中后续字段依赖前序 ref loader 字段
- **THEN** 计划构建阶段必须将该依赖反映到 `ref_loader_sequence` 排序

### Requirement: lookup_key 与 lookup_cast/诊断
系统 SHALL 使用 `to_field` 或目标 source 的 `key` 作为 lookup key;当 `to_field` 为非 key 字段时,loader 返回映射的 key 必须匹配该字段.
系统 SHALL 在 lookup 前对 `from` 值应用 `lookup_cast`(step 级优先,缺省使用 source 级),支持 `auto`/`int`/`str`/`sep_first`,多字段关联逐字段应用并在任一字段缺失或转换失败时忽略该键.
`auto_normalize_key` 规则: None/NaN->None,float->None(触发采样诊断告警),bool->0/1,int/str 保持,Decimal 可整数化则转 int 否则回退 `auto_str_normalize`,其他类型回退 `auto_str_normalize`.
诊断告警文案应提示配置 `lookup_cast`/`value_cast` 或调整 relation 定义,并复用跨模块统一常量.

#### Scenario: step 级 lookup_cast
- **WHEN** step 配置 `lookup_cast: {name: sep_first, sep: ","}` 且 `from` 为 "1,2,3"
- **THEN** lookup key 为 "1"(再按 auto_normalize_key 规则归一化)

#### Scenario: 浮点被拒绝
- **WHEN** `lookup_cast: {name: auto}` 且外键值为 123.0 或 12.34
- **THEN** 归一化结果为 None 且该键被忽略,并触发诊断告警事件

#### Scenario: 多字段缺失
- **WHEN** 多字段关联中任一 from_field 为 None
- **THEN** 该键不参与关联查找

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

### Requirement: legacy `to_bind` is rejected with a copy-pastable migration hint
系统 MUST 将 step 级 `to_bind` 视为 legacy 写法并在校验阶段 fail-fast.
错误信息 MUST 明确指出应将绑定迁移到“目标 source 的 `params` 模板”,并给出可直接照抄的替换建议片段(至少覆盖常见 `use_keys.param` 形态)。

#### Scenario: relation step `to_bind.use_keys.param` 被拒绝并给迁移建议
- **WHEN** 某个 relation step 中出现 `to_bind: {use_keys: {param: ids}}`
- **THEN** 校验 MUST 失败并指向该 step 的配置路径
- **AND** 错误信息 MUST 包含可直接照抄的替换建议片段(示例):
  ```yaml
  sources:
    <to_source_id>:
      params:
        ids:
          $keys: {as: set}
  ```

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

### Requirement: ref loader 依赖信号驱动稳定排序
系统 MUST 基于 relation/lookup steps 推断 ref loader 依赖信号并构建 `ref_loader_sequence`.
当依赖信号不足时 MUST 使用稳定回退顺序并输出可观测降级告警,不得静默退化.
依赖推断函数 MUST 为纯函数并覆盖关键 edge cases(空 steps、自身依赖、重复依赖、非 ref 字段依赖).

#### Scenario: 多级 relation 排序正确
- **WHEN** 关系链存在 `A -> B -> C` 且 `B/C` 都是 ref loader
- **THEN** 排序结果 MUST 保证 `B` 在 `C` 之前

### Requirement: 关联诊断基于样本值并支持复合键对比
系统 SHALL 基于样本值(而非样本 key)执行类型兼容检查;仅在存在完整样本时输出类型告警.
复合键诊断 MUST 按字段顺序逐一比较并输出可读对比结果;缺失值样本标记为 missing.
当类型不匹配且未配置 cast 时,诊断 SHOULD 给出 `lookup_cast` 建议.

#### Scenario: 样本值一致不报类型不兼容
- **WHEN** 样本 key 类型不同但样本字段值类型一致
- **THEN** 系统不应报告类型不兼容

### Requirement: 关联路径与比较输出可读且稳定
系统 SHALL 输出包含 step 序号、`source.field`、`[KEY]/[LOOKUP_KEY]` 与 cast 信息的路径文本.
对比表格输出列结构应稳定;无样本时返回明确空结果提示(如 `No comparison data`).

#### Scenario: 空样本返回空结果提示
- **WHEN** comparisons 为空列表
- **THEN** 返回文本应为 `No comparison data`

### Requirement: relation `from` MAY reference pre-relation derived fields on main_source side
系统 SHALL 允许 relation steps 的 `from` 引用顶层 derived field 作为 join key，但必须满足严格边界：
- 仅允许出现在 `from`（main_source 侧），`to` MUST NOT 引用 derived fields
- 引用语法仍为 `source.field`：当 `source==main_source.source_id` 且 `field` 命中顶层 derived field 时视为合法
- 仅允许引用 “pre-relation 可计算” 的 derived field：其依赖闭包 MUST NOT 包含任何需要 `LoadRef` 才能得到的字段（ref 字段/带 relation 的字段）
- 当违反以上约束时，系统 MUST 在编译/校验阶段 fail-fast 并输出可诊断错误（包含阻塞依赖链摘要）
- 当 relation `from` 依赖 derived field 时，系统 MUST 在该 relation 对应的 LoadRef 发生前完成该 derived field 的计算

#### Scenario: broadcast constant derived key can be used as relation `from`
- **GIVEN** 顶层 derived field `_broadcast_key` 定义为常量（例如 `compute: "1"`）
- **AND** 某个 relation step 的 `from` 使用 `<main_source_id>._broadcast_key`
- **WHEN** demand 被编译并执行
- **THEN** relation 校验 MUST 通过
- **AND** LoadRef 的 lookup key MUST 可读到 `_broadcast_key` 的计算值

#### Scenario: derived key that depends on ref fields is rejected
- **GIVEN** 某 derived field `k` 的 dependencies 中包含一个 ref 字段（必须经 LoadRef 才能得到）
- **WHEN** relation step 的 `from` 引用 `<main_source_id>.k`
- **THEN** 配置校验 MUST 失败并指出 `k` 不是 pre-relation 可计算

## Notes
- rows 模式传入的批次行上下文来自 BatchContext,仅包含 required_fields 内的字段.
- rows 模式默认批次内复用;若 loader 依赖可变的 batch_rows 或有副作用,应在目标 source 的 `params` 模板中使用 `$rows: {cache_mode: none}` 禁用复用.
- `$keys.as=list` 仅保证 keys-list 的顺序稳定可重复(与 `PYTHONHASHSEED` 无关);由于 keys 通常先以 set 去重,因此不承诺保持输入行出现顺序.如需自定义顺序,请在 loader 内自行排序/归并.
- path 推断仅基于已声明 relations 的有向 steps 构图.
- `lookup_cast` 仅影响关联键,不影响字段值输出.
- `value_cast: auto` 使用 `auto_str_normalize` 并在字段值写入上下文前执行(详见 `field-compute`).
