## MODIFIED Requirements

### Requirement: workflow workbook exports MUST escape Excel formulas by default
当 workflow 通过共享 `books.kind=xlsx_file` 或 `books.kind=xlsx_memory.export_xlsx` 导出 `.xlsx` 时,系统 MUST 默认保留所有字符串 cell 值原样写出,不得执行公式前缀转义。

防护模式（不可信输入显式收紧）：

- 若 effective book 配置 `allow_formulas=false`,系统 MUST 对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

#### Scenario: allow_formulas is true by default and preserves raw strings
- **GIVEN** workflow 声明 book 资源 `report` 且未显式设置 `allow_formulas`
- **WHEN** 某个写入节点将字符串 `\"=1+1\"` 写入该 book
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"=1+1\"`

#### Scenario: allow_formulas false escapes formula-like strings
- **GIVEN** workflow 声明 book 资源 `report` 且设置 `allow_formulas=false`
- **WHEN** 某个写入节点将字符串 `\"=1+1\"` 写入该 book
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`

### Requirement: workflow workbook resource authoring surface MUST support allow_formulas
系统 MUST 支持 workflow YAML 的 book 资源声明包含可选字段 `workflow.resources.books.<book_id>.allow_formulas`：

- 该字段 MUST 为 bool
- 缺省时 MUST 等价于 `true`

#### Scenario: book allow_formulas passes schema validation
- **WHEN** workflow YAML 声明 `workflow.resources.books.report.allow_formulas=false`
- **THEN** schema-only 校验 MUST 通过

