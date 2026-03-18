## MODIFIED Requirements

### Requirement: 字段值 value_cast
系统 SHALL 在字段值被加载或关联获取后应用 `value_cast` 转换,并支持以下取值:`auto`、`int`、`str`.

- `value_cast` 仅作用于源字段(非 compute 字段).
- 未声明 `value_cast` 时保持原值.
- 当原始值为 `None` 时,系统 MUST 透传 `None`(不做类型转换),不得将其转换为 `"None"` 等 truthy 字符串,也不得抛出转换异常。

#### Scenario: 应用字段 value_cast
- **WHEN** 字段 `amount` 配置 `value_cast: int` 且原始值为 "123"
- **THEN** 写入结果应为整数 123

#### Scenario: `value_cast: str` 对 None 透传
- **WHEN** 字段 `ratio` 配置 `value_cast: str` 且原始值为 `None`
- **THEN** 写入结果 MUST 为 `None`

#### Scenario: `value_cast: int` 对 None 透传
- **WHEN** 字段 `count` 配置 `value_cast: int` 且原始值为 `None`
- **THEN** 写入结果 MUST 为 `None`

#### Scenario: 缺省不转换
- **WHEN** 字段未配置 `value_cast`
- **THEN** 系统应保留原始值

