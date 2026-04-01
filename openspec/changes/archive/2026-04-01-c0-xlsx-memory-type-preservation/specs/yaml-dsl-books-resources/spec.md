## MODIFIED Requirements

### Requirement: `books.kind=xlsx_memory` MUST define in-memory budget guards and optional export_xlsx
系统 MUST 定义 `resources.books.<id>.kind=xlsx_memory` 的内存 book 预算护栏、typed internal semantics 与可选导出语义。

当 `resources.books.<id>.kind=xlsx_memory` 时,该 book 表示 workflow scope 的内存工作簿,并满足:

- `budget` MUST 存在且 MUST 为 mapping
- `budget.max_sheets` MUST 为整数且 `>=1`
- `budget.max_total_cells` MUST 为整数且 `>=1`
- internal rows MUST 使用 canonical field key + preserved `FieldValue` values 作为 SSOT
- workflow 内部非结束节点若经由 `xlsx_memory` 传递数据,系统 MUST 保留基础类型,而不是强制走字符串化路径
- 若上游内部值为 `Decimal`,系统 MUST 在 `xlsx_memory` internal path 中保持该 `Decimal`,不得隐式降级为 `float`
- 本要求只约束 internal preservation,不定义 `compute/call_by` 如何产生 `Decimal`

可选导出:

- `export_xlsx` MAY 存在且 MUST 为 mapping
- `export_xlsx.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `export_xlsx.write_lock` MUST 为 bool(默认 `false`)
- `export_xlsx.allow_formulas` MUST 为 bool(默认 `false`)
- spreadsheet/export 专属字符串转义与序列化 MUST 仅在最终 `export_xlsx` commit 边界生效

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

#### Scenario: xlsx_memory internal path keeps exact numeric values
- **GIVEN** 上游 output 写入 `resources.books.report.kind=xlsx_memory`
- **AND** 某字段值为 `Decimal("9.99")`
- **WHEN** 该值在 workflow 内部继续经由 `book_sheet_rows` 被下游节点读取
- **THEN** 读取结果 MUST 保持为 `Decimal`
- **AND** 系统 MUST NOT 在 internal path 中将其改写为字符串或 `float`

### Requirement: downstream demands MUST be able to load xlsx_memory book sheet rows via a built-in loader
系统 MUST 提供一个 workflow scope 的内置 loader,允许下游 demand 将上游 `xlsx_memory` book 的某个 sheet 作为 rows 输入使用:

- loader 稳定导入路径: `scalim.workflow.loaders:book_sheet_rows`
- YAML builtin callable id: `^workflow/book_sheet_rows`(由 `yaml-dsl-builtin-callables` 约束)
- `book_sheet_rows` MUST 以 canonical field key 作为返回 row 的键 SSOT
- `book_sheet_rows` MUST 返回保留 `FieldValue` 值域的 row values,而不是 `CSV` 等价字符串 values

loader MUST 接收 `params.ref` 映射对象,并满足以下结构:

- `ref.node`（上游 node id）
- `ref.book`（book 资源 id）
- `ref.sheet`（sheet 名）

约束:

- 下游 node 仅允许读取其依赖闭包内上游 nodes 的 book(闭包可见性)
- 当引用越界或目标 sheet 不存在时,系统 MUST fail-fast 并提供可诊断摘要
- display header MUST NOT 泄漏到 loader 返回键空间
- loader MUST NOT 依赖猜测性字符串恢复来满足 typed row 语义

#### Scenario: reading a non-dependency book sheet is rejected
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 的 demand 通过内置 loader 引用 node A 的 book sheet
- **THEN** 系统 MUST fail-fast 并报告“引用超出 deps 可见范围”

#### Scenario: xlsx_memory sheet rows keep typed values
- **GIVEN** node A 写入 `books.kind=xlsx_memory` 的 `metrics` sheet
- **AND** 某 row 包含 `{"order_count": 5, "amount": Decimal("1.20"), "paid": True, "code": "007"}`
- **WHEN** node B 使用 `^workflow/book_sheet_rows(ref)` 读取 `metrics` sheet
- **THEN** `order_count` MUST 为 `int`
- **AND** `amount` MUST 为 `Decimal`
- **AND** `paid` MUST 为 `bool`
- **AND** `code` MUST 保持为字符串 `"007"`
