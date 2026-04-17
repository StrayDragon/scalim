# yaml-dsl-books-resources (delta)

## MODIFIED Requirements

### Requirement: `books.kind=xlsx_memory` MUST define in-memory budget guards and optional export_xlsx

系统 MUST 定义 `resources.books.<id>.kind=xlsx_memory` 的内存 book 预算护栏、typed internal semantics 与可选导出语义。

当 `resources.books.<id>.kind=xlsx_memory` 时,该 book 表示 workflow scope 的内存工作簿,并满足:

- `budget` MAY 存在,且当存在时 MUST 为 mapping
- 当 `budget` 存在时:
  - `budget.max_sheets` MUST 为整数且 `>=1`
  - `budget.max_total_cells` MUST 为整数且 `>=1`
- 当 `budget` 缺省时,系统 MUST 将其视为 **unlimited**(不启用预算护栏检查)
- internal rows MUST 使用 canonical field key + preserved `FieldValue` values 作为 SSOT
- workflow 内部非结束节点若经由 `xlsx_memory` 传递数据,系统 MUST 保留基础类型,而不是强制走字符串化路径
- 若上游内部值为 `Decimal`,系统 MUST 在 `xlsx_memory` internal path 中保持该 `Decimal`,不得隐式降级为 `float`
- 本要求只约束 internal preservation,不定义 `compute/call_by` 如何产生 `Decimal`

可选导出:

- `export_xlsx` MAY 存在且 MUST 为 mapping
- `export_xlsx.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `export_xlsx.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2）
- `export_xlsx.allow_formulas` MUST 为 bool(默认 `false`)
- 系统 MUST 基于 `book_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/books/<book_id>.xlsx`

legacy `export_xlsx.write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示。

#### Scenario: xlsx_memory budget can be omitted
- **GIVEN** `resources.books.report.kind=xlsx_memory`
- **WHEN** `resources.books.report.budget` 缺失
- **THEN** 编译/校验 MUST 成功

#### Scenario: xlsx_memory export_xlsx root can be injected via init_vars
- **GIVEN** `resources.books.report.kind=xlsx_memory`
- **AND** `resources.books.report.export_xlsx.path={$init_var: out_root}`
- **WHEN** 调用方提供 `init_vars={\"out_root\": \"./out\"}`
- **THEN** 编译期解析 MUST 成功

### Requirement: books MUST support default write behavior and per-output overrides for append vs sheet semantics

系统 MUST 允许在 book 级别配置默认写入行为,并允许 outputs 按需覆盖:

- `resources.books.<id>.write_defaults` MAY 存在且 MUST 为 mapping
  - `mode` MUST 为 `sheet|append` 之一(默认 `sheet`)
  - `align_by` MUST 为 `field_id|header` 之一(默认 `field_id`; 仅 `append` 生效)
  - `header_policy` MUST 为 `once|always|never` 之一(默认 `once`; 仅 `append` 生效)
  - `on_mismatch` MUST 为 `error|warn|skip` 之一(默认 `error`; 仅 `append` 生效)
  - `on_conflict` MUST 为 `error|overwrite|skip` 之一(默认 `error`; 仅 `sheet` 生效)
- `resources.books.<id>.write_defaults` MUST NOT 暴露通用 header 字段(`include_header`/`header_fields_output_by`)

outputs 级覆盖:

- `outputs[*].write` MAY 存在且 MUST 为 mapping
- `outputs[*].write` MAY 覆盖 `write_defaults` 的 book 专属字段集合,并 MAY 提供通用 header 字段:
  - `include_header`
  - `header_fields_output_by`
- effective `mode=append` 时,`outputs[*].write.include_header` MUST NOT 显式声明(避免与 `header_policy` 重叠)
- `outputs[*].write` 不得包含输出定义层字段(`fields/where/from/aggregate`)
- 对 `books.kind=xlsx_memory`, 内部链路 MUST 仅使用 canonical field key
- 对 `books.kind=xlsx_memory`, `write.header_fields_output_by` MUST 仅影响最终 `.xlsx` 导出显示
- 对 `books.kind=xlsx_memory`, effective `mode=append` + `align_by=header` MUST fail-fast

#### Scenario: write_defaults.mode defaults to sheet
- **GIVEN** `resources.books.report.kind=xlsx_file`
- **WHEN** `resources.books.report.write_defaults` 缺省
- **THEN** effective `write_defaults.mode` MUST 等于 `sheet`

#### Scenario: book write_defaults are schema-valid
- **WHEN** `resources.books.report.write_defaults.mode=append`
- **AND** `resources.books.report.write_defaults.align_by=field_id`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: xlsx_memory output-local header selection does not change internal keys
- **GIVEN** `resources.books.metrics.kind=xlsx_memory`
- **AND** output 绑定 `to.book=metrics`
- **AND** output effective `header_fields_output_by=name`
- **WHEN** 下游 demand 通过 `^workflow/book_sheet_rows` 读取该 sheet
- **THEN** 返回 row 的键 MUST 仍然是 canonical field key
- **AND** 该配置仅 MAY 影响 `export_xlsx` 的最终导出表头

#### Scenario: xlsx_memory append header alignment is rejected
- **GIVEN** `resources.books.metrics.kind=xlsx_memory`
- **AND** effective `mode=append`
- **WHEN** 用户声明 `align_by=header`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示 `xlsx_memory` 内部仅允许按 canonical field key 对齐

