## ADDED Requirements

### Requirement: xlsx_memory sheetbook MUST treat canonical field keys as the only internal row key space
系统 MUST 将 `xlsx_memory` / `sheetbook` 的内部字段键空间限制为 canonical field key:

- sheetbook 内部 baseline header MUST 以 canonical field key 作为 SSOT
- `iter_sheetbook_sheet_rows` / `book_sheet_rows` MUST 始终基于该 canonical baseline 产出 rows
- `name` / 自定义 header / display header MUST NOT 进入内部 rows、索引或读取路径

#### Scenario: book_sheet_rows reads canonical keys from a name-based export sheet
- **GIVEN** `xlsx_memory` sheet 的最终导出 header 使用字段 `name`
- **WHEN** 下游 node 调用 `book_sheet_rows`
- **THEN** 返回 row MUST 使用 canonical field key
- **AND** 下游 `normalize.index_by_key` 等逻辑 MUST 可直接使用这些键

### Requirement: xlsx_memory export header metadata MUST remain result-side only
系统 MUST 将 `xlsx_memory` 的导出 header 视为结果侧元信息:

- 当 book 配置了 `export_xlsx` 时,系统 MAY 为每个 sheet 维护导出 header metadata
- 该 metadata MUST 仅用于最终 `.xlsx` 表头渲染
- 该 metadata MUST 存放在 `sheetbook` plan 内部结构中
- 该 metadata MUST NOT 改变内部 rows 的字段键空间
- 同一 sheet 的导出 header metadata MUST 采用单一确定性基线,后续写入 MUST NOT 静默替换

#### Scenario: export uses result-side metadata without changing internal keys
- **GIVEN** `xlsx_memory` sheet 已建立导出 header metadata
- **WHEN** workflow 在结束时导出 `export_xlsx`
- **THEN** `.xlsx` 表头 MUST 使用该 metadata 渲染
- **AND** `book_sheet_rows` 返回键 MUST 保持为 canonical field key

#### Scenario: export header baseline cannot be silently replaced
- **GIVEN** 某 `xlsx_memory` sheet 已建立导出 header metadata 基线
- **WHEN** 后续写入尝试为同一 sheet 提供不同的导出 header metadata
- **THEN** 系统 MUST fail-fast
- **AND** 系统 MUST NOT 静默采用后写入的 header baseline

### Requirement: xlsx_memory append alignment MUST reject header-based semantics
系统 MUST 禁止 `xlsx_memory` 在 append 语义中使用 header-based 对齐:

- 对 `xlsx_memory`, append 对齐 MUST 只允许按 canonical field key
- 对 `xlsx_memory`, `align_by=header` MUST 被视为非法配置
- 该非法配置 MUST 在现有校验边界内尽早 fail-fast,并给出迁移提示

#### Scenario: append with header alignment is rejected for xlsx_memory
- **GIVEN** 某 `xlsx_memory` sheet 追加写入
- **WHEN** effective `align_by=header`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示改为 canonical field key 对齐
