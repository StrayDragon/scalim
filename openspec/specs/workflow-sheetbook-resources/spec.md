# workflow-sheetbook-resources Specification

**状态: ✅ 已实现**

## Purpose
定义 workflow YAML 的共享 `.xlsx` book 资源(以 `workflow.resources.books` 表达)的迁移约束与运行期契约: 预算护栏、确定性写入、冲突安全、可观测且可原子导出为最终 xlsx,并提供可稳定引用的内置 loader 供下游节点读取 sheet rows.
## Requirements
### Requirement: legacy sheetbook authoring surface MUST be rejected and migrated to books
系统 MUST 将旧 sheetbook authoring surface 视为已移除,并在 workflow 入口给出可操作迁移路径:

- workflow YAML MUST NOT 接受任何 legacy sheetbook resource group / write intents authoring surface
- 系统 MUST 提示迁移到:
  - `workflow.resources.books.<book_id>.kind=xlsx_memory|xlsx_file`
  - demand outputs 的 `outputs[*].to`/`outputs[*].write` 绑定(SSOT: `yaml-dsl-books-resources`)

#### Scenario: legacy sheetbooks are rejected with migration hint
- **WHEN** workflow YAML 包含任何 legacy sheetbook authoring surface
- **THEN** workflow 校验 MUST fail-fast
- **AND** 错误信息 MUST 包含迁移提示(迁移到 `workflow.resources.books` 与 demand outputs 的 `to/write`)

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
- 该要求仅约束 runtime/internal path 的保真传输,不承诺 `.xlsx` 文件格式的 Python 类型 round-trip

#### Scenario: final export preserves exact numeric internal values
- **GIVEN** 某 `xlsx_memory` sheet 内部 row 包含 `Decimal("12.30")`
- **WHEN** workflow 在结束时执行 `export_xlsx`
- **THEN** 系统 MUST 在最终 export 边界处理该值
- **AND** 系统 MUST NOT 在更早的 internal path 中把该值改写为字符串或 `float`
