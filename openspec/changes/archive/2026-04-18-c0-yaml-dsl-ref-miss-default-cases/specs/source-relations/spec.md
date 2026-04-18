# source-relations (delta) Specification

## MODIFIED Requirements

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
