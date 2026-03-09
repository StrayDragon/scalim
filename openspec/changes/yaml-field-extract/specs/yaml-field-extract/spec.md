## ADDED Requirements

### Requirement: `extract` reads values relative to the current row value for the active key
系统 SHALL 支持在源字段上声明 `extract`,并将其解释为相对“当前 key 对应的 row value”的字段读取路径,而不是相对外层 `loader_result` 映射。

`extract` 的根节点 MUST 等价于:
- 主加载路径中的 `result[row_id]`
- 关联加载路径中的 `result[lookup_key]`

系统 MUST 只隐式省略最外层 `lookup_key -> value` 包装,不得额外隐式跳过 row value 内部的第一层字段。

#### Scenario: 嵌套 dict 相对当前 row value 解析
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {"CustomerMark": {"clearn_reason_level": 2}, "review_status": 1}
  ```
- **WHEN** 字段配置为 `extract: CustomerMark.clearn_reason_level`
- **THEN** 字段值 MUST 解析为 `2`

#### Scenario: 内部包裹层不会被自动跳过
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {"payload": {"CustomerMark": {"clearn_reason_level": 2}}}
  ```
- **WHEN** 字段配置为 `extract: CustomerMark.clearn_reason_level`
- **THEN** 字段值 MUST 解析为 `None`
- **AND** 只有将配置改为 `extract: payload.CustomerMark.clearn_reason_level` 才能读取到 `2`

### Requirement: `extract` path traversal is segment-wise and uses the existing getter semantics
系统 MUST 将 `extract` 视为点分段路径,并对每个 segment 逐层复用现有 flat getter 语义:
- 先按 mapping key 读取
- 再按对象属性读取
- 最后尝试 `__getitem__`

任一 segment 缺失时,系统 MUST 返回 `None`.
v1 MUST 拒绝空 segment / 连续点 / 首尾点,且 MUST NOT 支持数组下标、通配符或转义点号。

#### Scenario: 对象属性可作为路径段读取
- **GIVEN** 当前 key 对应的 row value 为一个对象,其 `CustomerMark` 属性下的 `clearn_reason_level` 为 `2`
- **WHEN** 字段配置为 `extract: CustomerMark.clearn_reason_level`
- **THEN** 字段值 MUST 解析为 `2`

#### Scenario: 缺失中间段返回 None
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {"CustomerMark": None}
  ```
- **WHEN** 字段配置为 `extract: CustomerMark.clearn_reason_level`
- **THEN** 字段值 MUST 为 `None`
