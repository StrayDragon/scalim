# yaml-dsl-books-resources Specification

## Purpose
TBD - created by archiving change c35-workflow-io-books-resources. Update Purpose after archive.
## Requirements
### Requirement: demand/workflow YAML MUST support `resources.books` as the unified Excel IO resource surface

系统 MUST 在 **demand** 与 **workflow** 两类 YAML 中提供一致的 `resources.books` 资源入口,用于声明“Excel book”资源,并作为唯一对外稳定术语(不再区分 workbook/sheetbook):

- demand: `resources.books.<book_id>`
- workflow: `workflow.resources.books.<book_id>`

其中 `<book_id>` MUST 为非空字符串,并且在同一个 `resources.books` mapping 内 MUST 唯一。

`resources.books.<book_id>` MUST 是 mapping,并且 MUST 包含:

- `kind`: `xlsx_file|xlsx_memory`

#### Scenario: demand resources.books passes schema-only validation
- **WHEN** demand YAML 声明 `resources.books.report.kind=xlsx_file`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: workflow resources.books passes schema-only validation
- **WHEN** workflow YAML 声明 `workflow.resources.books.report.kind=xlsx_memory`
- **THEN** schema-only 校验 MUST 通过

### Requirement: `books.kind=xlsx_file` MUST define file export semantics and path resolution base
系统 MUST 定义 `resources.books.<id>.kind=xlsx_file` 的文件导出语义与路径解析基准。

当 `resources.books.<id>.kind=xlsx_file` 时,该 book 表示一个最终落盘的 `.xlsx` 文件,并满足:

- `resources.books.<id>.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- 相对路径 MUST 以**声明该 book 的 YAML 文件所在目录**为基准解析(不是进程 CWD)
- 系统 MUST 在实际写入前创建父目录(`mkdir(parents=True, exist_ok=True)`)

可选字段:

- `allow_formulas` MUST 为 bool(默认 `false`)
- `write_lock` MUST 为 bool(默认 `false`)

#### Scenario: xlsx_file book requires a path
- **GIVEN** `resources.books.report.kind=xlsx_file`
- **WHEN** `resources.books.report.path` 缺失或为空
- **THEN** 编译/校验 MUST fail-fast
- **AND** 错误信息 MUST 指向 `resources.books.report.path`

#### Scenario: xlsx_file relative path is resolved against the YAML directory
- **GIVEN** demand YAML 位于 `/a/b/report.demand.yaml`
- **AND** `resources.books.report.kind=xlsx_file`
- **AND** `resources.books.report.path=./out/report.xlsx`
- **WHEN** 系统解析该 book 的输出路径
- **THEN** 解析结果 MUST 等价于 `/a/b/out/report.xlsx`(经 `resolve` 归一化)

### Requirement: `books.kind=xlsx_memory` MUST define in-memory budget guards and optional export_xlsx
系统 MUST 定义 `resources.books.<id>.kind=xlsx_memory` 的内存 book 预算护栏与可选导出语义。

当 `resources.books.<id>.kind=xlsx_memory` 时,该 book 表示 workflow scope 的内存工作簿,并满足:

- `budget` MUST 存在且 MUST 为 mapping
- `budget.max_sheets` MUST 为整数且 `>=1`
- `budget.max_total_cells` MUST 为整数且 `>=1`

可选导出:

- `export_xlsx` MAY 存在且 MUST 为 mapping
- `export_xlsx.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `export_xlsx.write_lock` MUST 为 bool(默认 `false`)
- `export_xlsx.allow_formulas` MUST 为 bool(默认 `false`)

#### Scenario: xlsx_memory budget is required
- **GIVEN** `resources.books.report.kind=xlsx_memory`
- **WHEN** `resources.books.report.budget` 缺失
- **THEN** 编译/校验 MUST fail-fast
- **AND** 错误信息 MUST 指向 `resources.books.report.budget`

#### Scenario: xlsx_memory export_xlsx path can be injected via init_vars
- **GIVEN** `resources.books.report.kind=xlsx_memory`
- **AND** `resources.books.report.export_xlsx.path={$init_var: out_path}`
- **WHEN** 调用方提供 `init_vars={"out_path": "./out/report.xlsx"}`
- **THEN** 编译期解析 MUST 成功

### Requirement: demand MUST bind outputs to books via `outputs_defaults.to.book` and `outputs[*].to`

系统 MUST 支持在 demand YAML 中将 outputs 绑定到 book 资源:

- `outputs_defaults.to.book` MAY 存在且 MUST 为非空字符串
- `outputs[*].to` MAY 存在且 MUST 为 mapping
  - `outputs[*].to.book` MAY 存在且 MUST 为非空字符串
  - `outputs[*].to.sheet` MAY 存在且 MUST 为非空字符串

默认/继承规则:

- 若 `outputs[*].to.book` 缺省,则从 `outputs_defaults.to.book` 继承
- 若 `outputs[*].to.sheet` 缺省,则 `sheet` MUST 默认等于 `outputs[*].name`
- `sheet` MUST 通过 Excel sheet 名校验(非空、长度 `<=31`、且不得包含 `\\ / ? * [ ] :`)
- 若某 output 的 effective `to.book` 缺失,系统 MUST fail-fast 并给出可复制迁移提示(例如提示设置 `outputs_defaults.to.book`)

#### Scenario: sheet defaults to output.name and is validated
- **GIVEN** `outputs_defaults.to.book: report`
- **AND** `outputs[0].name: metrics`
- **AND** `outputs[0].to` 缺省
- **WHEN** 系统计算 effective IO binding
- **THEN** `outputs[0]` MUST 绑定到 book=`report`, sheet=`metrics`

#### Scenario: invalid default sheet name fails fast
- **GIVEN** `outputs_defaults.to.book: report`
- **AND** `outputs[0].name` 长度大于 31
- **WHEN** 系统计算 effective IO binding
- **THEN** MUST fail-fast
- **AND** 错误信息 MUST 指向 `outputs[0].name` 并提示显式提供 `outputs[0].to.sheet`

### Requirement: standalone demand MUST fail-fast when a referenced book resource is missing

系统 MUST 在 standalone `compile/run` 执行 demand 时,对所有 outputs 的 effective `to.book`(来自 `outputs_defaults.to.book` 或 `outputs[*].to.book`)执行资源存在性校验,并在缺失时 fail-fast:

- 系统 MUST 确保该 `book_id` 在 effective `resources.books` 中存在
- 若缺失,系统 MUST fail-fast(不得静默降级为“无输出”或“写到临时路径”)
- 错误信息 MUST 同时包含:
  - 缺失的 `book_id`
  - 发生位置(例如 `outputs_defaults.to.book` 或 `outputs[0].to.book`)
  - 可复制迁移提示(例如: “在 demand 中声明 `resources.books.<id>` 或在 Python overrides 的 `overrides.resources.books` 提供该资源”)

#### Scenario: missing book id fails fast with actionable hint
- **GIVEN** demand 声明 `outputs_defaults.to.book: report`
- **AND** demand 未声明 `resources.books.report`
- **WHEN** 调用方执行 standalone `compile/run` 且未提供 `overrides.resources.books.report`
- **THEN** MUST fail-fast
- **AND** 错误信息 MUST 提示如何补齐 `resources.books.report`

### Requirement: workflow MUST merge books from demand/workflow with deterministic precedence and strict contracts

系统 MUST 定义 `books` 的合并/覆盖优先级(从低到高):

1) demand YAML 的 `resources.books`
2) workflow YAML 的 `workflow.resources.books`(同名 `<book_id>` 覆盖)
3) Python overrides(同名 `<book_id>` 最终覆盖)

约束:

- 覆盖同名 `<book_id>` 时,系统 MUST 校验 effective book 仍满足其 `kind` 的必填字段约束
- 系统 MUST 在 kind 不兼容时 fail-fast(例如未知 kind,或 YAML 结构与 kind 不匹配)

#### Scenario: workflow overrides a demand book path
- **GIVEN** demand 声明 `resources.books.report: {kind: xlsx_file, path: ./out/a.xlsx}`
- **AND** workflow 声明 `workflow.resources.books.report: {kind: xlsx_file, path: ./out/b.xlsx}`
- **WHEN** workflow 运行该 demand
- **THEN** effective `report.path` MUST 等于 `./out/b.xlsx`(以 workflow YAML 目录为基准解析)

### Requirement: books MUST support default write behavior and per-output overrides for append vs sheet semantics

系统 MUST 允许在 book 级别配置默认写入行为,并允许 outputs 按需覆盖:

- `resources.books.<id>.write_defaults` MAY 存在且 MUST 为 mapping
  - `mode` MUST 为 `sheet|append` 之一(默认 `append`)
  - `align_by` MUST 为 `field_id|header` 之一(默认 `field_id`; 仅 `append` 生效)
  - `header_policy` MUST 为 `once|always|never` 之一(默认 `once`; 仅 `append` 生效)
  - `on_mismatch` MUST 为 `error|warn|skip` 之一(默认 `error`; 仅 `append` 生效)
  - `on_conflict` MUST 为 `error|overwrite|skip` 之一(默认 `error`; 仅 `sheet` 生效)

outputs 级覆盖:

- `outputs[*].write` MAY 存在且 MUST 为 mapping
- `outputs[*].write` 仅允许覆盖 write_defaults 的上述字段集合,不得包含输出定义层字段(`fields/where/from/aggregate`)

#### Scenario: book write_defaults are schema-valid
- **WHEN** `resources.books.report.write_defaults.mode=append`
- **AND** `resources.books.report.write_defaults.align_by=field_id`
- **THEN** schema-only 校验 MUST 通过

### Requirement: Excel exports MUST escape formula-like strings by default (opt-out via allow_formulas)

当系统导出 `.xlsx`(包括 `xlsx_file` book 与 `xlsx_memory.export_xlsx`)时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：

- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

允许公式（可信输入显式放宽）：

- 若 effective book 配置 `allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: allow_formulas false escapes formula-like strings
- **GIVEN** `resources.books.report.kind=xlsx_file`
- **AND** `resources.books.report.allow_formulas` 缺省(等价 `false`)
- **WHEN** 写入字符串 `\"=1+1\"` 到任一 sheet cell
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`

### Requirement: downstream demands MUST be able to load xlsx_memory book sheet rows via a built-in loader

系统 MUST 提供一个 workflow scope 的内置 loader,允许下游 demand 将上游 `xlsx_memory` book 的某个 sheet 作为 rows 输入使用:

- loader 稳定导入路径: `scalim.workflow.loaders:book_sheet_rows`
- YAML builtin callable id: `^workflow/book_sheet_rows`(由 `yaml-dsl-builtin-callables` 约束)

loader MUST 接收 `params.ref` 映射对象,并满足以下结构:

- `ref.node`（上游 node id）
- `ref.book`（book 资源 id）
- `ref.sheet`（sheet 名）

约束:

- 下游 node 仅允许读取其依赖闭包内上游 nodes 的 book(闭包可见性)
- 当引用越界或目标 sheet 不存在时,系统 MUST fail-fast 并提供可诊断摘要

#### Scenario: reading a non-dependency book sheet is rejected
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 的 demand 通过内置 loader 引用 node A 的 book sheet
- **THEN** 系统 MUST fail-fast 并报告“引用超出 deps 可见范围”

### Requirement: `.xlsx` outputs MUST use books binding; `container.type: workbook` MUST be rejected (BREAKING)

系统 MUST 将 `.xlsx` 输出的用户侧 authoring surface 收敛到 `resources.books` + outputs→book 绑定,并拒绝 `outputs[*].container.type: workbook` 写法(避免双路径导致心智负担与实现漂移).

约束:

- `outputs[*].container.type=workbook` MUST 在 schema-only 与 runtime semantic 校验阶段被拒绝
- `outputs[*].container.sheet/allow_formulas/write_lock` MUST 不再作为输出层 authoring surface(其语义移动到 `outputs[*].to.sheet` 与 `resources.books.*` 中)
- 若用户仍需要 CSV 文件输出,仍可继续使用 `outputs[*].container.type=csv` + 非空 `path`

#### Scenario: schema rejects workbook container type deterministically
- **WHEN** demand YAML 包含 `outputs[0].container.type=workbook`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 提示迁移到 `resources.books` + `outputs_defaults.to.book` / `outputs[*].to`

