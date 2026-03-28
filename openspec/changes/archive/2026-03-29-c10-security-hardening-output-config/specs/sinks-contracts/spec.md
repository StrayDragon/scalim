## ADDED Requirements

### Requirement: CSV sinks MUST escape spreadsheet formulas by default

当使用内建 CSV sinks 输出数据时,系统 MUST 提供“公式注入防护”能力,避免不可信字符串在 Excel 等工具中被当作公式执行或触发外连.

系统 MUST 支持两种模式:
- **escape**(默认): 将疑似公式的字符串以文本形式写出(例如前缀转义),确保工具不会将其作为公式执行
- **allow**: 允许将字符串原样写入,使其可被工具当作公式解析(用于可信场景主动写公式)

系统 MUST 明确规定“疑似公式字符串”的识别规则(至少覆盖 `=`, `+`, `-`, `@` 前缀,允许忽略前导空白).

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头与数据行。

#### Scenario: escape mode writes formula-like values as text
- **GIVEN** 某个输出字段来自不可信输入且值为字符串 `=HYPERLINK("http://evil", "x")`
- **WHEN** CSV sink 以默认 escape 模式写出该值
- **THEN** 输出的 CSV 字段值 MUST 以 `'` 前缀写出,以避免被解析为公式

#### Scenario: allow mode preserves raw values
- **GIVEN** 用户显式启用 allow 模式且输出值为字符串 `=1+1`
- **WHEN** CSV sink 写出该值
- **THEN** 输出的 CSV 字段值 MUST 保持为 `=1+1`

