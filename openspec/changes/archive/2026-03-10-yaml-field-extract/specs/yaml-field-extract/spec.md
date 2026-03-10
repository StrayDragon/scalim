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

### Requirement: `extract` is a dot+bracket path expression with typed segments
系统 MUST 将 `extract` 解析为一串 segments(typed),并在运行时按 segments 执行逐段读取。

语法(无歧义、无隐式 cast):
- `a.b.c`: string identifier segments
- `[1]`: int key segment(用于 `row[1]` 这类非字符串 key)
- `["a.b"]` / `['a.b']`: string key segment(用于字面量含点号/空格/特殊字符的 key)

约束:
- dot identifier segment MUST 匹配标识符语法(例如 `CustomerMark`),不支持 `a-b`/`a b` 之类;这类 key 必须用 bracket string segment 表达
- 系统 MUST NOT 做 `"1" -> 1` 或 `1 -> "1"` 的自动转换,避免歧义
- v1 MUST NOT 支持数组下标语义: `[1]` 永远表示 “key=1”,不是 list index(即使中间值是 list/tuple,也不得把 `[1]` 当索引)
- bracket int segment 的语法 MUST 为非负十进制整数(`[0-9]+`),不得包含符号位或空白(例如 `[-1]`、`[ 1 ]` 均非法)
- bracket string segment 支持最小转义,以允许表达包含引号或反斜杠的 key:
  - `\\` 表示字面量 `\`
  - `\"` 仅在 `["..."]` 中表示字面量 `"`
  - `\'` 仅在 `['...']` 中表示字面量 `'`
  - 其它 `\x` 形式 MUST fail-fast(避免引入不清晰的逃逸语义)
- v1 MUST 在编译/校验阶段拒绝非法表达式(空 segment/连续点/首尾点/未闭合括号或引号等,以及非法转义)

#### Scenario: bracket int key 读取 int-key nested dict
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {1: {"clearn_reason_level": 2}, 2: {"clearn_reason_level": 1}, "review_status": 0}
  ```
- **WHEN** 字段配置为 `extract: "[1].clearn_reason_level"`
- **THEN** 字段值 MUST 解析为 `2`

#### Scenario: bracket string key 读取 dotted literal key
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {"a.b": {"x": 1}}
  ```
- **WHEN** 字段配置为 `extract: '["a.b"].x'`
- **THEN** 字段值 MUST 解析为 `1`

#### Scenario: no implicit cast between `"1"` and `1`
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {"1": {"x": 1}, 1: {"x": 2}}
  ```
- **WHEN** 字段配置为 `extract: "[1].x"`
- **THEN** 字段值 MUST 解析为 `2`
- **AND** 当字段配置为 `extract: '["1"].x'` 时,字段值 MUST 解析为 `1`

#### Scenario: v1 不支持 list/tuple 索引
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  [{"x": 0}, {"x": 1}]
  ```
- **WHEN** 字段配置为 `extract: "[1].x"`
- **THEN** 字段值 MUST 为 `None`

#### Scenario: bracket string segment 支持最小转义
- **GIVEN** 当前 key 对应的 row value 为:
  ```python
  {"a\"b": 1, "a\\b": 2}
  ```
- **WHEN** 字段配置为 `extract: '["a\"b"]'`
- **THEN** 字段值 MUST 解析为 `1`
- **AND** 当字段配置为 `extract: '["a\\b"]'` 时,字段值 MUST 解析为 `2`

#### Scenario: whitespace 与负数 int segment 被拒绝
- **WHEN** 字段配置为 `extract: "[ 1 ].x"` 或 `extract: "[-1].x"`
- **THEN** 编译或校验 MUST 失败并报告配置路径

### Requirement: segment-wise traversal reuses the existing getter semantics
系统 MUST 对每个 segment 逐层复用既有 getter 风格(按顺序尝试):
- 先按 mapping key 读取
- 对 string segment 可回退到对象属性读取
- 最后尝试 `__getitem__`

任一 segment 缺失时,系统 MUST 返回 `None`.

#### Scenario: 对象属性可作为 string segment 读取
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
