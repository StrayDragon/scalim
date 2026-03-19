## MODIFIED Requirements

### Requirement: 字段值 value_cast
系统 SHALL 在字段值被加载或关联获取后应用 `value_cast` 转换,并支持以下取值:`auto`、`int`、`str`、`decimal`.

- `value_cast` 仅作用于源字段(非 compute 字段).
- 未声明 `value_cast` 时保持原值.
- 当原始值为 `None` 时,系统 MUST 透传 `None`(不做类型转换),不得将其转换为 `"None"` 等 truthy 字符串,也不得抛出转换异常。
- 当 `value_cast: decimal` 时:
  - 系统 MUST 将值转换为 `decimal.Decimal`
  - 对 `str` 值系统 MUST 先 `strip()`；strip 后为空字符串时系统 MUST 返回 `None`
  - 对 `float` 值系统 MUST 使用 `Decimal(str(value))` 转换,避免 `Decimal(float)` 的二进制精确展开导致“意外小数”

#### Scenario: 应用字段 value_cast
- **WHEN** 字段 `amount` 配置 `value_cast: int` 且原始值为 "123"
- **THEN** 写入结果应为整数 123

#### Scenario: `value_cast: decimal` 基本转换
- **WHEN** 字段 `price` 配置 `value_cast: decimal` 且原始值为 "123.45"
- **THEN** 写入结果 MUST 为 `Decimal("123.45")`

#### Scenario: `value_cast: decimal` 对 float 使用 str 转换
- **WHEN** 字段 `ratio` 配置 `value_cast: decimal` 且原始值为 0.1
- **THEN** 写入结果 MUST 为 `Decimal("0.1")`

#### Scenario: `value_cast: decimal` 对空白字符串视为缺失
- **WHEN** 字段 `amount` 配置 `value_cast: decimal` 且原始值为 "   "
- **THEN** 写入结果 MUST 为 `None`

#### Scenario: `value_cast: str` 对 None 透传
- **WHEN** 字段 `ratio` 配置 `value_cast: str` 且原始值为 `None`
- **THEN** 写入结果 MUST 为 `None`

#### Scenario: `value_cast: int` 对 None 透传
- **WHEN** 字段 `count` 配置 `value_cast: int` 且原始值为 `None`
- **THEN** 写入结果 MUST 为 `None`

#### Scenario: 缺省不转换
- **WHEN** 字段未配置 `value_cast`
- **THEN** 系统应保留原始值

## ADDED Requirements

### Requirement: compute 表达式允许使用 `Decimal(...)` 构造器
系统 MUST 在 compute 安全引擎的白名单函数中包含 `Decimal`,以支持在表达式中使用 `Decimal("0.1")` 等写法显式避免 `float` 精度问题。

#### Scenario: compute 使用 Decimal 字符串字面量
- **WHEN** 派生字段配置 `compute: "Decimal('0.1') + Decimal('0.2')"`
- **THEN** 该表达式校验 MUST 通过且执行结果 MUST 为 `Decimal('0.3')`

