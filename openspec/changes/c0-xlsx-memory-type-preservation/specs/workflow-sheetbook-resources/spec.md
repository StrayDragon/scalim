## ADDED Requirements

### Requirement: xlsx_memory sheetbook MUST preserve typed internal rows for workflow reads
系统 MUST 将 `xlsx_memory` 的内部 sheetbook rows 定义为 typed internal rows,而不是 `CSV` 等价字符串 rows:

- sheetbook internal baseline header MUST 继续使用 canonical field key
- sheetbook internal rows/segments MUST 保留 `FieldValue` 值域
- workflow-managed output 写入 `xlsx_memory` 时,MUST NOT 先以字符串 rows 作为内部 SSOT
- `book_sheet_rows` / `iter_sheetbook_sheet_rows` 读取内部 rows 时,MUST 直接返回保留原始基础类型的值
- 系统 MUST NOT 依赖猜测性 `_auto_cast` / 启发式字符串恢复来满足该能力

#### Scenario: xlsx_memory read keeps numeric and boolean field values typed
- **GIVEN** 上游 workflow node 向某个 `xlsx_memory` sheet 写入 `{"order_count": 5, "amount": Decimal("1.20"), "paid": True}`
- **WHEN** 下游 node 通过 `book_sheet_rows` 读取该 sheet
- **THEN** 返回 row 中 `order_count` MUST 为 `int`
- **AND** `amount` MUST 为 `Decimal`
- **AND** `paid` MUST 为 `bool`

#### Scenario: xlsx_memory read does not guess-cast string-looking values
- **GIVEN** 上游 workflow node 向某个 `xlsx_memory` sheet 写入 `{"code": "007", "raw_text": ""}`
- **WHEN** 下游 node 通过 `book_sheet_rows` 读取该 sheet
- **THEN** `code` MUST 保持为字符串 `"007"`
- **AND** `raw_text` MUST 保持为字符串 `""`

### Requirement: xlsx_memory spreadsheet serialization MUST happen only at final export boundary
系统 MUST 将 `xlsx_memory` 的 spreadsheet/export 转换限制在最终 commit/export 边界:

- internal rows MUST NOT 因为未来可能导出 `.xlsx` 而提前统一字符串化
- `export_xlsx` 在最终写 workbook 时,MUST 仅对 `str` 应用 spreadsheet formula escaping 规则
- 对 `int` / `bool` / `Decimal` / `float` / `None`,系统 MUST 保持 typed cell value 语义,不得先统一 `str(...)`
- 若上游 internal row 已经是 `Decimal`,系统 MUST NOT 在内部路径将其隐式降级为 `float`

#### Scenario: final export preserves exact numeric internal values
- **GIVEN** 某 `xlsx_memory` sheet 内部 row 包含 `Decimal("12.30")`
- **WHEN** workflow 在结束时执行 `export_xlsx`
- **THEN** 系统 MUST 在最终 export 边界处理该值
- **AND** 系统 MUST NOT 在更早的 internal path 中把该值改写为字符串或 `float`
