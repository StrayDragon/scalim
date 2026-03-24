# workflow-sheetbook-resources Specification

## ADDED Requirements

### Requirement: sheetbook xlsx export MUST escape Excel formulas by default
当 workflow 声明 `sheetbook` 资源并配置 `workflow.resources.sheetbooks.<id>.export_xlsx.path` 导出 `.xlsx` 时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

允许公式（可信输入显式放宽）：
- 若 `workflow.resources.sheetbooks.<id>.export_xlsx.allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: sheetbook export escapes formula-like values by default
- **GIVEN** workflow 声明 `sheetbook` 资源并启用 `export_xlsx.path`,且未显式设置 `export_xlsx.allow_formulas`
- **WHEN** 某个 sheet 被写入包含 `\"@HYPERLINK(\\\"http://example\\\",\\\"x\\\")\"` 的字符串 cell 值
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 以 `'` 前缀转义（例如 `\"'@HYPERLINK(\\\"http://example\\\",\\\"x\\\")\"`）

#### Scenario: sheetbook export allow_formulas opt-out preserves raw strings
- **GIVEN** workflow 声明 `workflow.resources.sheetbooks.report.export_xlsx.allow_formulas=true`
- **WHEN** 写入字符串 `\"-1+2\"` 到导出的 sheetbook
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 仍为 `\"-1+2\"`

### Requirement: sheetbook export_xlsx authoring surface MUST support allow_formulas
系统 MUST 支持 workflow YAML 的 sheetbook 导出配置 `workflow.resources.sheetbooks.<id>.export_xlsx` 包含可选字段 `allow_formulas`：

- `workflow.resources.sheetbooks.<id>.export_xlsx.allow_formulas` MUST 为 bool
- 缺省时 MUST 等价于 `false`

#### Scenario: sheetbook export_xlsx allow_formulas passes schema validation
- **WHEN** workflow YAML 声明 `workflow.resources.sheetbooks.report.export_xlsx.allow_formulas=false`
- **THEN** schema-only 校验 MUST 通过
