## MODIFIED Requirements

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

- `resources.books.<id>.xlsx_file.allow_formulas` MUST 为 bool(默认 `false`)

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
- 当 `budget` 缺省时,系统 MUST 将其视为 **unlimited**(不启用预算护栏检查)
- internal rows MUST 使用 canonical field key + preserved `FieldValue` values 作为 SSOT
- workflow 内部非结束节点若经由 `xlsx_memory` 传递数据,系统 MUST 保留基础类型,而不是强制走字符串化路径
- 若上游内部值为 `Decimal`,系统 MUST 在 `xlsx_memory` internal path 中保持该 `Decimal`,不得隐式降级为 `float`
- 本要求只约束 internal preservation,不定义 `compute/call_by` 如何产生 `Decimal`

可选导出:

- `resources.books.<id>.xlsx_memory.export_xlsx` MAY 存在且 MUST 为 mapping
- `resources.books.<id>.xlsx_memory.export_xlsx.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `resources.books.<id>.xlsx_memory.export_xlsx.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2）
- `resources.books.<id>.xlsx_memory.export_xlsx.allow_formulas` MUST 为 bool(默认 `false`)
- 系统 MUST 基于 `book_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/books/<book_id>.xlsx`

legacy `export_xlsx.write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示。

#### Scenario: xlsx_memory budget can be omitted
- **GIVEN** `resources.books.report.xlsx_memory` 被选择
- **WHEN** `resources.books.report.xlsx_memory.budget` 缺失
- **THEN** 编译/校验 MUST 成功

#### Scenario: xlsx_memory export_xlsx root can be injected via init_vars
- **GIVEN** `resources.books.report.xlsx_memory.export_xlsx.path={$init_var: out_root}`
- **WHEN** 调用方提供 `init_vars={\"out_root\": \"./out\"}`
- **THEN** 编译期解析 MUST 成功

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

当 workflow compile 对 `workflow.resources.books.<book_id>`（以及其嵌套字段如 `write_defaults` / `xlsx_memory.budget` / `xlsx_memory.export_xlsx`）应用 patch/overlay 时，系统 MUST 提供严格且可预测的契约校验：

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

当系统导出 `.xlsx`(包括 `xlsx_file` book 与 `xlsx_memory.export_xlsx`)时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：

- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

允许公式（可信输入显式放宽）：

- 若 effective `xlsx_file` 分支声明 `resources.books.<id>.xlsx_file.allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。
- 若 effective `xlsx_memory` 分支声明 `resources.books.<id>.xlsx_memory.export_xlsx.allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: allow_formulas false escapes formula-like strings
- **GIVEN** `resources.books.report.xlsx_file.path=./out`
- **AND** `resources.books.report.xlsx_file.allow_formulas` 缺省(等价 `false`)
- **WHEN** 写入字符串 `\"=1+1\"` 到任一 sheet cell
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`
