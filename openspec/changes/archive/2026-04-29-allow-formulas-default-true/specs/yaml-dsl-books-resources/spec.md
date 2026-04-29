## MODIFIED Requirements

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

