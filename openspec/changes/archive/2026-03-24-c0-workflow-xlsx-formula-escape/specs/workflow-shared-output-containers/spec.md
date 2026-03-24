# workflow-shared-output-containers Specification

## ADDED Requirements

### Requirement: workflow workbook exports MUST escape Excel formulas by default
当 workflow 通过共享 `workbook` 资源导出 `.xlsx` 时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

允许公式（可信输入显式放宽）：
- 若 `workflow.resources.workbooks.<workbook_id>.allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: formula-like values are escaped by default
- **GIVEN** workflow 声明 workbook 资源 `report` 且未显式设置 `workflow.resources.workbooks.report.allow_formulas`
- **WHEN** 某个 write intent 将字符串 `\"=1+1\"` 与 `\"  +SUM(A1:A2)\"` 写入该 workbook
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 分别为 `\"'=1+1\"` 与 `\"'  +SUM(A1:A2)\"`

#### Scenario: allow_formulas opt-out preserves raw strings
- **GIVEN** workflow 声明 `workflow.resources.workbooks.report.allow_formulas=true`
- **WHEN** 某个 write intent 将字符串 `\"=1+1\"` 写入该 workbook
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 仍为 `\"=1+1\"`

### Requirement: workflow workbook resource authoring surface MUST support allow_formulas
系统 MUST 支持 workflow YAML 的 workbook 资源声明包含可选字段 `workflow.resources.workbooks.<workbook_id>.allow_formulas`：

- 该字段 MUST 为 bool
- 缺省时 MUST 等价于 `false`

#### Scenario: workbook allow_formulas passes schema validation
- **WHEN** workflow YAML 声明 `workflow.resources.workbooks.report.allow_formulas=false`
- **THEN** schema-only 校验 MUST 通过
