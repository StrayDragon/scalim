# language: zh-CN
# capability: workflow-sheetbook-resources
# purpose: 定义 workflow YAML 的共享 `.xlsx` book 资源(以 `workflow.resources.books` 表达)的迁移约束与运行期契约: 确定性写入、冲突安全、可观测且可原子导出为最终 xlsx,并提供可稳定引用的内置 loader 供下游节点读取 sheet rows（不再提供 cell/sheet 预算护栏）. [scope-review-2026-07-20-c999]
# scope: src/scalim/

功能: workflow-sheetbook-resources

  @req:r98 @human
  场景: legacy sheetbook authoring surface MUST be rejected and migrated to books
    - 系统 MUST 将旧 sheetbook authoring surface 视为已移除,并在 workflow 入口给出可操作迁移路径: - workflow YAML MUST NOT 接受任何 legacy sheetbook resource group / write intents authoring surface - 系统 MUST 提示迁移到: - `workflow.resources.books.<book_id>.xlsx`（有 path=pathful 落盘；无 path=pathless 内存总线） - demand outputs 的 `outputs[*].to`/`outputs[*].write` 绑定(SSOT: `yaml-dsl-books-resources`)

  @req:r340 @human
  场景: pathless sheetbook MUST treat canonical field keys as the only internal row key
    - 系统 MUST 将 pathless xlsx / `sheetbook` 的内部字段键空间限制为 canonical field key: - sheetbook 内部 baseline header MUST 以 canonical field key 作为 SSOT - `iter_sheetbook_sheet_rows` / `book_sheet_rows` MUST 始终基于该 canonical baseline 产出 rows - `name` / 自定义 header / display header MUST NOT 进入内部 rows、索引或读取路径

  @req:r462 @human
  场景: pathless sheetbook export header metadata MUST remain result-side only
    - 系统 MUST 将 pathless sheetbook 的导出 header 视为结果侧元信息: - 当 book 最终需要落盘导出时,系统 MAY 为每个 sheet 维护导出 header metadata - 该 metadata MUST 仅用于最终 `.xlsx` 表头渲染 - 该 metadata MUST 存放在 `sheetbook` plan 内部结构中 - 该 metadata MUST NOT 改变内部 rows 的字段键空间 - 同一 sheet 的导出 header metadata MUST 采用单一确定性基线,后续写入 MUST NOT 静默替换

  @req:r547 @human
  场景: pathful book export path errors MUST point to xlsx.path authoring surface
    - 当准备 pathful book 的版本化输出 root 时，若 runtime 错误可归因到导出 path，系统 MUST 提供可操作的配置定位路径： - `ScalimWorkflowConfigError.path` MUST 指向 `workflow.resources.books.<book_id>.xlsx.path` - message MAY 包含内部资源提示（例如 `resource_type=workbook`/`sheetbook`），但 MUST NOT 替换上述 user-facing path

  @req:r617 @human
  场景: pathless append alignment MUST reject header-based semantics
    - 系统 MUST 禁止 pathless xlsx / sheetbook 在 append 语义中使用 header-based 对齐: - append 对齐 MUST 只允许按 canonical field key - `align_by=header` MUST 被视为非法配置 - 该非法配置 MUST 在现有校验边界内尽早 fail-fast,并给出迁移提示

  @req:r666 @human
  场景: pathless sheetbook MUST preserve typed internal rows for workflow reads
    - 系统 MUST 将 pathless xlsx / sheetbook 的内部 rows 定义为 typed internal rows,而不是 `CSV` 等价字符串 rows: - sheetbook internal baseline header MUST 继续使用 canonical field key - sheetbook internal rows/segments MUST 保留 `FieldValue` 值域 - workflow-managed output 写入 pathless book 时,MUST NOT 先以字符串 rows 作为内部 SSOT - `book_sheet_rows` / `iter_sheetbook_sheet_rows` 读取内部 rows 时,MUST 直接返回保留原始基础类型的值 - 系统 MUST NOT 依赖猜测性 `_auto_cast` / 启发式字符串恢复来满足该能力

  @req:r708 @human
  场景: pathless spreadsheet serialization MUST happen only at final export boundary
    - 系统 MUST 将 pathless sheetbook 的 spreadsheet/export 转换限制在最终 commit/export 边界: - internal rows MUST NOT 因为未来可能导出 `.xlsx` 而提前统一字符串化 - 最终写 workbook 时,MUST 仅对 `str` 应用 spreadsheet formula escaping 规则 - 对 `int` / `bool` / `Decimal` / `float` / `None`,系统 MUST 保持 typed cell value 语义,不得先统一 `str(...)` - 若上游 internal row 已经是 `Decimal`,系统 MUST NOT 在内部路径将其隐式降级为 `float` - 该要求仅约束 runtime/internal path 的保真传输,不承诺 `.xlsx` 文件格式的 Python 类型 round-trip

  @req:r742 @human
  场景: pathless book MUST NOT enforce cell/sheet budget guards
    - 系统 MUST NOT 再对 pathless/pathful xlsx 强制执行 cell/sheet 预算护栏（BookBudgetPolicy 已移除）。YAML 残留 budget MUST fail-fast 并提示删除。其余 sheetbook typed/export/canonical-key 契约保持不变。
  @req:r98 @human
  场景: legacy-sheetbooks-are-rejected-with-migration-hint
    - 必须成立：当 workflow YAML 包含任何 legacy sheetbook authoring surface；那么 workflow 校验 MUST fail-fast
    当 workflow YAML 包含任何 legacy sheetbook authoring surface
    那么 workflow 校验 MUST fail-fast
  @req:r340 @human
  场景: book-sheet-rows-reads-canonical-keys-from-a-name-based-expor
    - 必须成立：假如 pathless sheet 的最终导出 header 使用字段 `name`；当 下游 node 调用 `book_sheet_rows`；那么 返回 row MUST 使用 canonical field key
    假如 pathless sheet 的最终导出 header 使用字段 `name`
    当 下游 node 调用 `book_sheet_rows`
    那么 返回 row MUST 使用 canonical field key
  @req:r462 @human
  场景: export-uses-result-side-metadata-without-changing-internal-k
    - 必须成立：假如 pathless sheet 已建立导出 header metadata；当 workflow 在结束时导出 `.xlsx`；那么 `.xlsx` 表头 MUST 使用该 metadata 渲染
    假如 pathless sheet 已建立导出 header metadata
    当 workflow 在结束时导出 `.xlsx`
    那么 `.xlsx` 表头 MUST 使用该 metadata 渲染

  @req:r462 @human
  场景: export-header-baseline-cannot-be-silently-replaced
    - 必须成立：假如 某 pathless sheet 已建立导出 header metadata 基线；当 后续写入尝试为同一 sheet 提供不同的导出 header metadata；那么 系统 MUST fail-fast
    假如 某 pathless sheet 已建立导出 header metadata 基线
    当 后续写入尝试为同一 sheet 提供不同的导出 header metadata
    那么 系统 MUST fail-fast
  @req:r547 @human
  场景: output-root-preparation-error-reports-xlsx-path
    - 必须成立：假如 a workflow uses `books.<book_id>.xlsx.path`；当 preparing the versioned output root fails (e.g. due to permission error or invalid path)；那么 the raised `ScalimWorkflowConfigError` MUST include `path=workflow.resources.books.<book_id>.xlsx.path`
    假如 a workflow uses `books.<book_id>.xlsx.path`
    当 preparing the versioned output root fails (e.g. due to permission error or invalid path)
    那么 the raised `ScalimWorkflowConfigError` MUST include `path=workflow.resources.books.<book_id>.xlsx.path`
  @req:r617 @human
  场景: append-with-header-alignment-is-rejected-for-pathless
    - 必须成立：假如 某 pathless sheet 追加写入；当 effective `align_by=header`；那么 系统 MUST fail-fast
    假如 某 pathless sheet 追加写入
    当 effective `align_by=header`
    那么 系统 MUST fail-fast
  @req:r666 @human
  场景: pathless-read-keeps-numeric-and-boolean-field-values-type
    - 必须成立：假如 上游 workflow node 向某个 pathless sheet 写入 `{"order_count": 5, "amount": Decimal("1.20"), "paid": True}`；当 下游 node 通过 `book_sheet_rows` 读取该 sheet；那么 返回 row 中 `order_count` MUST 为 `int`
    假如 上游 workflow node 向某个 pathless sheet 写入 `{"order_count": 5, "amount": Decimal("1.20"), "paid": True}`
    当 下游 node 通过 `book_sheet_rows` 读取该 sheet
    那么 返回 row 中 `order_count` MUST 为 `int`

  @req:r666 @human
  场景: pathless-read-does-not-guess-cast-string-looking-values
    - 必须成立：假如 上游 workflow node 向某个 pathless sheet 写入 `{"code": "007", "raw_text": ""}`；当 下游 node 通过 `book_sheet_rows` 读取该 sheet；那么 `code` MUST 保持为字符串 `"007"`
    假如 上游 workflow node 向某个 pathless sheet 写入 `{"code": "007", "raw_text": ""}`
    当 下游 node 通过 `book_sheet_rows` 读取该 sheet
    那么 `code` MUST 保持为字符串 `"007"`
  @req:r708 @human
  场景: final-export-preserves-exact-numeric-internal-values
    - 必须成立：假如 某 pathless sheet 内部 row 包含 `Decimal("12.30")`；当 workflow 在结束时执行最终导出；那么 系统 MUST 在最终 export 边界处理该值
    假如 某 pathless sheet 内部 row 包含 `Decimal("12.30")`
    当 workflow 在结束时执行最终导出
    那么 系统 MUST 在最终 export 边界处理该值

  @req:r742 @human
  场景: yaml-residual-budget-rejected
    - 必须成立：假如 YAML resources.books 声明 budget；当 用户执行 validate；那么 系统 MUST fail-fast 并提示删除该字段
    假如 YAML resources.books 声明 budget
    当 用户执行 validate
    那么 系统 MUST fail-fast 并提示删除该字段

  @req:r742 @human
  场景: no-runtime-cell-sheet-budget
    - 必须成立：假如 pathless 或 pathful book 均无预算配置；当 写入多 sheet / 多 cell；那么 系统 MUST NOT 因已移除的 max_sheets/max_total_cells 护栏 fail-fast
    假如 pathless 或 pathful book 均无预算配置
    当 写入多 sheet / 多 cell
    那么 系统 MUST NOT 因已移除的 max_sheets/max_total_cells 护栏 fail-fast
