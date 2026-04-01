## MODIFIED Requirements

### Requirement: books MUST support default write behavior and per-output overrides for append vs sheet semantics
系统 MUST 允许在 book 级别配置默认写入行为,并允许 outputs 按需覆盖:

- `resources.books.<id>.write_defaults` MAY 存在且 MUST 为 mapping
  - `mode` MUST 为 `sheet|append` 之一(默认 `append`)
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
- 对 `books.kind=xlsx_memory`,内部链路 MUST 仅使用 canonical field key; `header_fields_output_by` MUST 仅决定最终 `.xlsx` 导出显示的 header
- 对 `books.kind=xlsx_memory`,effective `align_by=header` MUST 被视为非法配置并 fail-fast

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

### Requirement: downstream demands MUST be able to load xlsx_memory book sheet rows via a built-in loader
系统 MUST 提供一个 workflow scope 的内置 loader,允许下游 demand 将上游 `xlsx_memory` book 的某个 sheet 作为 rows 输入使用:

- loader 稳定导入路径: `scalim.workflow.loaders:book_sheet_rows`
- YAML builtin callable id: `^workflow/book_sheet_rows`(由 `yaml-dsl-builtin-callables` 约束)
- `book_sheet_rows` MUST 以 canonical field key 作为返回 row 的键 SSOT, independent of any exported header display mode

loader MUST 接收 `params.ref` 映射对象,并满足以下结构:

- `ref.node`（上游 node id）
- `ref.book`（book 资源 id）
- `ref.sheet`（sheet 名）

约束:

- 下游 node 仅允许读取其依赖闭包内上游 nodes 的 book(闭包可见性)
- 当引用越界或目标 sheet 不存在时,系统 MUST fail-fast 并提供可诊断摘要
- display header MUST NOT 泄漏到 loader 返回键空间

#### Scenario: reading a non-dependency book sheet is rejected
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 的 demand 通过内置 loader 引用 node A 的 book sheet
- **THEN** 系统 MUST fail-fast 并报告“引用超出 deps 可见范围”

#### Scenario: xlsx_memory sheet rows stay on canonical keys when export uses names
- **GIVEN** node A 写入 `books.kind=xlsx_memory` 的 `metrics` sheet
- **AND** 该 output effective `header_fields_output_by=name`
- **WHEN** node B 使用 `^workflow/book_sheet_rows(ref)` 读取 `metrics` sheet
- **THEN** row 键 MUST 为 canonical field key
- **AND** row 键 MUST NOT 变为字段 `name`
