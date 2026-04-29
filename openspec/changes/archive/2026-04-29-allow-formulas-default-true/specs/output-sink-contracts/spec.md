## MODIFIED Requirements

### Requirement: File sinks MUST support formula injection protection
当使用内建 file sinks (CSV/Excel) 输出数据时，系统 MUST 提供”公式注入防护”能力，避免不可信字符串在电子表格工具中被当作公式执行。

系统 MUST 支持两种模式：
- **allow** (默认): 允许将字符串原样写入，使其可被工具当作公式解析（用于可信场景主动写公式）
- **escape**: 将疑似公式的字符串以文本形式写出（例如前缀转义），确保工具不会将其作为公式执行（用于不可信输入）

系统 MUST 明确规定”疑似公式字符串”的识别规则（至少覆盖 `=`, `+`, `-`, `@` 前缀，允许忽略前导空白）。

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）
- 若原始字符串以 `'` 开头，MUST 保持不变（避免重复转义）
- 对 `value.lstrip()` 的首字符，若属于 `{ '=', '+', '-', '@' }`，MUST 在**原始值**前追加 `'`
- 该规则 MUST 同时作用于表头与数据行

#### Scenario: default mode preserves raw values
- **GIVEN** 用户使用内建 file sink 且未显式启用 escape 模式
- **AND** 输出值为字符串 `=1+1`
- **WHEN** file sink 写出该值
- **THEN** 输出的字段值 MUST 保持为 `=1+1`

#### Scenario: escape mode writes formula-like values as text
- **GIVEN** 某个输出字段来自不可信输入且值为字符串 `=HYPERLINK(“http://evil”, “x”)`
- **WHEN** file sink 以 escape 模式写出该值
- **THEN** 输出的字段值 MUST 以 `'` 前缀写出，以避免被解析为公式

