# yaml-dsl-books-resources Specification

## Purpose
定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义.
## Requirements
### Requirement: demand/workflow YAML MUST support `resources.books` as the unified Excel IO resource surface

系统 MUST 在 **demand** 与 **workflow** 两类 YAML 中提供一致的 `resources.books` 资源入口,用于声明“Excel book”资源,并作为唯一对外稳定术语(不再区分 workbook/sheetbook):

- demand: `resources.books.<book_id>`
- workflow: `workflow.resources.books.<book_id>`

其中 `<book_id>` MUST 为非空字符串,并且在同一个 `resources.books` mapping 内 MUST 唯一。

`resources.books.<book_id>` MUST 是 mapping,并且 MUST 选择且仅选择一个实现分支：

- `xlsx_file: <mapping>`
- `xlsx_memory: <mapping>`

并且 MAY 额外声明公共字段:

- `write_defaults: <mapping>`

legacy `kind` discriminator MUST 被移除；若用户仍声明 `resources.books.<book_id>.kind`，系统 MUST fail-fast 并给出迁移提示（迁移到 `resources.books.<book_id>.<variant>` 分支写法）。

（demand-only）imports 支持：

- demand YAML MAY 在 `resources.books.<book_id>` 节点级声明 `$import`（导入整个资源节点 mapping）
- demand YAML MAY 在 `resources.books.<book_id>.<variant>` 分支级声明 `$import`（仅导入分支字段，同时保留节点级公共字段如 `write_defaults`）
- 当 `$import` 与本地键并存时，imports expansion MUST 以“导入值为 defaults、本地覆盖导入值”的语义合并；展开后的 effective mapping MUST 仍满足 exactly-one variant 契约
- workflow YAML MUST NOT 支持 `imports`/`$import`（schema 与 runtime 均 fail-fast）

#### Scenario: demand resources.books passes schema-only validation
- **WHEN** demand YAML 声明 `resources.books.report.xlsx_file.path=./out`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: demand node-level $import passes schema-only validation
- **WHEN** demand YAML 声明 `resources.books.report.$import=common.resources.books.report`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: demand branch-level $import passes schema-only validation
- **WHEN** demand YAML 声明 `resources.books.report.xlsx_file.$import=common.resources.books.report_xlsx_file`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: workflow resources.books passes schema-only validation
- **WHEN** workflow YAML 声明 `workflow.resources.books.report.xlsx_memory: {}`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: legacy kind discriminator is rejected with migration hint
- **WHEN** 用户仍声明 `resources.books.report.kind=xlsx_file`
- **THEN** schema-only 与 runtime 校验 MUST fail-fast
- **AND** 错误信息 MUST 提示迁移到 `resources.books.report.xlsx_file: {...}` 形态

### Requirement: `books.kind=xlsx_file` MUST define file export semantics and path resolution base

系统 MUST 定义 `resources.books.<id>.xlsx_file` 的文件导出语义与路径解析基准。

当 `resources.books.<id>.xlsx_file` 分支被选择时,该 book 表示一个版本化输出 root 下的 `.xlsx` 导出,并满足:

- `resources.books.<id>.xlsx_file.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `resources.books.<id>.xlsx_file.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2），而不是最终 `.xlsx` 文件路径
- 相对路径 MUST 以**声明该 book 的 YAML 文件所在目录**为基准解析(不是进程 CWD)
- 系统 MUST 在实际写入前创建父目录(`mkdir(parents=True, exist_ok=True)`)
- 系统 MUST 基于 `book_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/books/<book_id>.xlsx`

可选字段:

- `resources.books.<id>.xlsx_file.allow_formulas` MUST 为 bool(默认 `true`)

legacy `write_lock` 配置面 MUST 被移除；若用户仍提供 `resources.books.<id>.write_lock`，系统 MUST fail-fast 并给出迁移提示。

#### Scenario: xlsx_file book requires a path
- **GIVEN** `resources.books.report.xlsx_file` 被选择
- **WHEN** `resources.books.report.xlsx_file.path` 缺失或为空
- **THEN** 编译/校验 MUST fail-fast
- **AND** 错误信息 MUST 指向 `resources.books.report.xlsx_file.path`

#### Scenario: xlsx_file relative path is resolved against the YAML directory
- **GIVEN** demand YAML 位于 `/a/b/report.demand.yaml`
- **AND** `resources.books.report.xlsx_file.path=./out`
- **WHEN** 系统解析该 book 的输出 root
- **THEN** 解析结果 MUST 等价于 `/a/b/out`(经 `resolve` 归一化)

### Requirement: `books.kind=xlsx_memory` MUST define in-memory budget guards and optional export_xlsx

系统 MUST 定义 `resources.books.<id>.xlsx_memory` 的内存 book 预算护栏、typed internal semantics 与可选导出语义。

当 `resources.books.<id>.xlsx_memory` 分支被选择时,该 book 表示 workflow scope 的内存工作簿,并满足:

- `resources.books.<id>.xlsx_memory.budget` MAY 存在,且当存在时 MUST 为 mapping
- 当 `resources.books.<id>.xlsx_memory.budget` 存在时:
  - `budget.max_sheets` MUST 为整数且 `>=1`
  - `budget.max_total_cells` MUST 为整数且 `>=1`
- 当 `resources.books.<id>.xlsx_memory.budget` 缺省时,系统 MUST 将其视为 **unlimited**(不启用预算护栏检查)
- internal rows MUST 使用 canonical field key + preserved `FieldValue` values 作为 SSOT
- workflow 内部非结束节点若经由 `xlsx_memory` 传递数据,系统 MUST 保留基础类型,而不是强制走字符串化路径
- 若上游内部值为 `Decimal`,系统 MUST 在 `xlsx_memory` internal path 中保持该 `Decimal`,不得隐式降级为 `float`
- 本要求只约束 internal preservation,不定义 `compute/call_by` 如何产生 `Decimal`

可选导出:

- `resources.books.<id>.xlsx_memory.export_xlsx` MAY 存在且 MUST 为 mapping
- `resources.books.<id>.xlsx_memory.export_xlsx.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `resources.books.<id>.xlsx_memory.export_xlsx.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2）
- `resources.books.<id>.xlsx_memory.export_xlsx.allow_formulas` MUST 为 bool(默认 `true`)
- 系统 MUST 基于 `book_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/books/<book_id>.xlsx`

legacy `export_xlsx.write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示。

#### Scenario: xlsx_memory budget can be omitted
- **GIVEN** `resources.books.report.xlsx_memory` 被选择
- **WHEN** `resources.books.report.xlsx_memory.budget` 缺失
- **THEN** 编译/校验 MUST 成功

#### Scenario: xlsx_memory export_xlsx root can be injected via init_vars
- **GIVEN** `resources.books.report.xlsx_memory` 被选择
- **AND** `resources.books.report.xlsx_memory.export_xlsx.path={$init_var: out_root}`
- **WHEN** 调用方提供 `init_vars={\"out_root\": \"./out\"}`
- **THEN** 编译期解析 MUST 成功

### Requirement: demand MUST bind outputs to books via `outputs[*].to.book` and `outputs[*].to.sheet`

系统 MUST 支持在 demand YAML 中将 Excel outputs 绑定到 book 资源,且绑定入口仅允许位于 output 局部:

- 对于绑定到 book 的 output,`outputs[*].to` MUST 存在且 MUST 为 mapping:
  - `outputs[*].to.book` MUST 为非空字符串
  - `outputs[*].to.sheet` MAY 为非空字符串

默认/继承规则:

- 若 `outputs[*].to.sheet` 缺省,则 `sheet` MUST 默认等于 `outputs[*].name`
- `sheet` MUST 通过 Excel sheet 名校验(非空、长度 `<=31`、且不得包含 `\\ / ? * [ ] :`)
- 若某 output 的 effective `to.book` 缺失,系统 MUST fail-fast 并给出可复制迁移提示(例如提示设置 `outputs[*].to.book`)

#### Scenario: sheet defaults to output.name and is validated
- **GIVEN** `outputs[0].name: metrics`
- **AND** `outputs[0].to.book: report`
- **AND** `outputs[0].to.sheet` 缺省
- **WHEN** 系统计算 effective IO binding
- **THEN** `outputs[0]` MUST 绑定到 book=`report`, sheet=`metrics`

#### Scenario: invalid default sheet name fails fast
- **GIVEN** `outputs[0].to.book: report`
- **AND** `outputs[0].name` 长度大于 31
- **WHEN** 系统计算 effective IO binding
- **THEN** MUST fail-fast
- **AND** 错误信息 MUST 指向 `outputs[0].name` 并提示显式提供 `outputs[0].to.sheet`

#### Scenario: books output can override header source at output-local write
- **WHEN** output 声明 `to.book=report`
- **AND** `write.header_fields_output_by=field_id`
- **THEN** 该 output 的表头来源 MUST 使用 `field_id`

#### Scenario: include_header is rejected for append-mode books output
- **GIVEN** output 绑定到某个 book
- **AND** effective `mode=append`
- **WHEN** 用户显式声明 `write.include_header`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示 `append` 模式应使用 `header_policy`

### Requirement: standalone demand MUST fail-fast when a referenced book resource is missing

系统 MUST 在 standalone `compile/run` 执行 demand 时,对所有 outputs 的 effective `to.book`(来自 `outputs[*].to.book`)执行资源存在性校验,并在缺失时 fail-fast:

- 系统 MUST 确保该 `book_id` 在 effective `resources.books` 中存在
- 若缺失,系统 MUST fail-fast(不得静默降级为“无输出”或“写到临时路径”)
- 错误信息 MUST 同时包含:
  - 缺失的 `book_id`
  - 发生位置(例如 `outputs[0].to.book`)
  - 可复制迁移提示(例如: “在 demand 中声明 `resources.books.<id>` 或在 Python overrides 的 `overrides.resources.books` 提供该资源”)

#### Scenario: missing book id fails fast with actionable hint
- **GIVEN** demand 声明 `outputs[0].to.book: report`
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

- 覆盖同名 `<book_id>` 时,系统 MUST 校验 effective book 仍满足其所选 variant 的必填字段约束
- 系统 MUST 在 variant 不兼容时 fail-fast(例如未知分支 key,或 YAML 结构与分支约束不匹配)

#### Scenario: workflow overrides a demand book path
- **GIVEN** demand 声明 `resources.books.report: {xlsx_file: {path: ./out/a}}`
- **AND** workflow 声明 `workflow.resources.books.report: {xlsx_file: {path: ./out/b}}`
- **WHEN** workflow 运行该 demand
- **THEN** effective `report.path` MUST 等于 `./out/b`(以 workflow YAML 目录为基准解析)

### Requirement: workflow book patches MUST be applied with strict contracts and consistent diagnostics

当 workflow compile 对 `workflow.resources.books.<book_id>`（以及其嵌套字段如 `write_defaults` / `budget` / `export_xlsx`）应用 patch/overlay 时，系统 MUST 提供严格且可预测的契约校验：

- 对任意 patch mapping，系统 MUST 检测 unknown keys 并 fail-fast
- 对任意字段类型不匹配（例如期望 bool 但得到 list），系统 MUST fail-fast 且诊断信息 MUST 指向准确逻辑 path
- 对 `write_defaults` 等枚举字段，系统 MUST 以一致口径校验并提供可行动错误提示
- 上述校验 SHOULD 由集中实现的 helper 承载，避免同类规则在不同入口漂移

#### Scenario: unknown book patch key fails fast with a precise path
- **GIVEN** 用户在 `workflow.resources.books.report` 中提供未知字段 `unknown_key`
- **WHEN** workflow compile 应用 book patch
- **THEN** 系统 MUST fail-fast
- **AND** 错误诊断 MUST 指向 `workflow.resources.books.report.unknown_key`

#### Scenario: nested write_defaults enum validation is consistent
- **GIVEN** 用户提供 `write_defaults.on_mismatch=not_a_policy`
- **WHEN** workflow compile 校验该配置
- **THEN** 系统 MUST fail-fast
- **AND** 错误 MUST 提示允许值集合（`error|warn|skip`）

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
- **GIVEN** `resources.books.report.xlsx_file.path=./out`
- **WHEN** `resources.books.report.write_defaults` 缺省
- **THEN** effective `write_defaults.mode` MUST 等于 `sheet`

#### Scenario: book write_defaults are schema-valid
- **GIVEN** `resources.books.report.xlsx_file.path=./out`
- **WHEN** `resources.books.report.write_defaults.mode=append`
- **AND** `resources.books.report.write_defaults.align_by=field_id`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: xlsx_memory output-local header selection does not change internal keys
- **GIVEN** `resources.books.metrics.xlsx_memory: {}`
- **AND** output 绑定 `to.book=metrics`
- **AND** output effective `header_fields_output_by=name`
- **WHEN** 下游 demand 通过 `^workflow/book_sheet_rows` 读取该 sheet
- **THEN** 返回 row 的键 MUST 仍然是 canonical field key
- **AND** 该配置仅 MAY 影响 `export_xlsx` 的最终导出表头

#### Scenario: xlsx_memory append header alignment is rejected
- **GIVEN** `resources.books.metrics.xlsx_memory: {}`
- **AND** effective `mode=append`
- **WHEN** 用户声明 `align_by=header`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示 `xlsx_memory` 内部仅允许按 canonical field key 对齐

### Requirement: Excel exports MUST escape formula-like strings by default (opt-out via allow_formulas)

当系统导出 `.xlsx`(包括 `xlsx_file` book 与 `xlsx_memory.export_xlsx`)时,系统 MUST 默认保留所有字符串 cell 值原样写出,不得执行公式前缀转义。

防护模式（不可信输入显式收紧）：

- 若 effective book 配置 `allow_formulas=false`,系统 MUST 对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：

- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

#### Scenario: allow_formulas is true by default and preserves raw strings
- **GIVEN** `resources.books.report.xlsx_file.path=./out`
- **AND** `resources.books.report.xlsx_file.allow_formulas` 缺省(等价 `true`)
- **WHEN** 写入字符串 `\"=1+1\"` 到任一 sheet cell
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"=1+1\"`

#### Scenario: allow_formulas false escapes formula-like strings
- **GIVEN** `resources.books.report.xlsx_file.path=./out`
- **AND** `resources.books.report.xlsx_file.allow_formulas=false`
- **WHEN** 写入字符串 `\"=1+1\"` 到任一 sheet cell
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`

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

### Requirement: `.xlsx` outputs MUST use books binding; legacy workbook container surface MUST be rejected (BREAKING)

系统 MUST 将输出 authoring surface 收敛到 `resources + outputs[*].to + outputs[*].write`,并移除 `outputs[*].container` 这条并行路径。

约束:

- `.xlsx` 输出 MUST 使用 `resources.books` + `outputs[*].to.book`
- CSV 输出 MUST 使用 `resources.files` + `outputs[*].to.file`
- `outputs[*].container` MUST 在 schema-only 与 runtime semantic 校验阶段被拒绝
- `outputs[*].to` MUST 成为唯一目标绑定入口
- `outputs[*].write` MUST 成为唯一写入策略入口

#### Scenario: legacy container output is rejected with migration hint
- **WHEN** demand YAML 仍声明 `outputs[*].container`
- **THEN** schema-only 与 runtime 校验 MUST fail-fast
- **AND** 错误信息 MUST 提示迁移到 `resources.files/resources.books` + `outputs[*].to` + `outputs[*].write`

