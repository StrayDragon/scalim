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
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py` (YAML → relation IR compilation)
- `src/IMPL_ROOT/planning/loader_ordering/deps.py` / `src/IMPL_ROOT/planning/loader_ordering/sequences.py`
- `src/IMPL_ROOT/utils/relation_diagnostics.py`
## Requirements
### Requirement: steps 结构与 relation 解析/推断规则
系统 SHALL 将关系定义为有序 `steps` 列表并按声明顺序执行;每个 step 包含 `from`/`to`(source.field 或同源列表)以及可选 `lookup_cast`/`to_bind`,相邻 steps 必须链式相连.
字段通过 `relation` 提供 steps 对象(允许 YAML alias 复用),不支持 relation_id 字符串引用.
若 `relation` 缺省且字段 source 不是 main_source,系统仅在唯一路径存在时自动推断;无路径或多路径时校验失败.
`relation` steps 必须以 main_source 为起点、以字段 source 为终点,并保持 left join 语义(未命中保持 None).
系统 MUST 将 steps 中的依赖字段用于 ref loader 排序信号构建,以驱动 `ref_loader_sequence` 的依赖排序.

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

### Requirement: bind/to_bind 结构与校验
系统 SHALL 支持在 step 中声明 `to_bind` 构造下游 loader 参数,缺省时使用 `sources.*.bind`;`use_keys` 传入 lookup keys,`use_rows` 传入 batch_rows.
`use_keys.as` 仅允许 `set`(默认)/`list`,`use_rows.cache_mode` 仅允许 `batch`(默认)/`none`;`to_bind` 必须且仅允许包含 `use_rows` 或 `use_keys` 之一.
若目标 source 为 `preload_forever`,可省略绑定.
当 `use_keys.as=list` 时,系统 MUST 输出稳定顺序的 keys 列表,不得受集合迭代顺序影响.

#### Scenario: keys 模式绑定
- **WHEN** step 声明 `to_bind: {use_keys: {param: ids}}`
- **THEN** loader 调用应传入 `ids=<lookup_keys>`

#### Scenario: to_bind 缺少 use 分支
- **WHEN** step 配置 `to_bind: {param: ids}` (旧语法)
- **THEN** 校验失败并提示需使用 `use_rows` 或 `use_keys`

#### Scenario: use_keys.as=list 顺序稳定
- **WHEN** step 声明 `to_bind: {use_keys: {param: ids, as: list}}` 且 lookup_keys 相同
- **THEN** 不同运行中的 `ids` 列表顺序必须一致

### Requirement: 批次内 LoadRef 复用与分片语义
系统 MUST 在同一批次内对 relation signature 完全一致的 LoadRef 字段进行 group 合并并一次执行;signature 由 steps 中的 to_source/from_fields/to_key/lookup_cast/binding 组成.
系统 MUST 基于 group 内字段构建 lookup_keys 并集并写回所有字段;若 relation 不一致则不得合并.
系统 MUST 复用同 relation/row_id/from_field 的 lookup key 归一化结果;不同 relation 不复用,且诊断事件仅在首次归一化时触发.
rows 模式默认复用,`to_bind.use_rows.cache_mode=none` 显式禁用;复用使用首次调用的 batch_rows 快照.
keys 模式支持 `lookup_chunk_size` 分片加载并合并结果;分片语义与一次性加载一致.

#### Scenario: 同 relation 多字段只执行一次
- **GIVEN** fields `f1/f2/f3` 指向同一 `source`,且 relation signature 完全一致
- **WHEN** 批次执行 LoadRef
- **THEN** 该 group 在该批次仅触发一次逻辑加载
- **AND** loader_context.field_keys 应为 `[f1, f2, f3]`

#### Scenario: rows 模式禁用复用
- **WHEN** relation 使用 rows 模式绑定且 `to_bind.use_rows.cache_mode=none`
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

## Notes
- rows 模式传入的批次行上下文来自 BatchContext,仅包含 required_fields 内的字段.
- rows 模式默认批次内复用;若 loader 依赖可变的 batch_rows 或有副作用,应显式配置 `to_bind.use_rows.cache_mode=none`.
- `use_keys.as=list` 仅保证 keys-list 的顺序稳定可重复(与 `PYTHONHASHSEED` 无关);由于 keys 通常先以 set 去重,因此不承诺保持输入行出现顺序.如需自定义顺序,请在 loader 内自行排序/归并.
- path 推断仅基于已声明 relations 的有向 steps 构图.
- `lookup_cast` 仅影响关联键,不影响字段值输出.
- `value_cast: auto` 使用 `auto_str_normalize` 并在字段值写入上下文前执行(详见 `field-compute`).
