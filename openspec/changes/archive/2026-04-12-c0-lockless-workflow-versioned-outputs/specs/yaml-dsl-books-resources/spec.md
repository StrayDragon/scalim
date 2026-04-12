# yaml-dsl-books-resources Specification

## MODIFIED Requirements

### Requirement: `books.kind=xlsx_file` MUST define file export semantics and path resolution base

系统 MUST 定义 `resources.books.<id>.kind=xlsx_file` 的文件导出语义与路径解析基准。

当 `resources.books.<id>.kind=xlsx_file` 时,该 book 表示一个版本化输出 root 下的 `.xlsx` 导出,并满足:

- `resources.books.<id>.path` MUST 为非空字符串或 `{$init_var: <name>}` 指令节点
- `resources.books.<id>.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2），而不是最终 `.xlsx` 文件路径
- 相对路径 MUST 以**声明该 book 的 YAML 文件所在目录**为基准解析(不是进程 CWD)
- 系统 MUST 在实际写入前创建父目录(`mkdir(parents=True, exist_ok=True)`)
- 系统 MUST 基于 `book_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/books/<book_id>.xlsx`

可选字段:

- `allow_formulas` MUST 为 bool(默认 `false`)

legacy `write_lock` 配置面 MUST 被移除；若用户仍提供 `resources.books.<id>.write_lock`，系统 MUST fail-fast 并给出迁移提示。

#### Scenario: xlsx_file book requires a path
- **GIVEN** `resources.books.report.kind=xlsx_file`
- **WHEN** `resources.books.report.path` 缺失或为空
- **THEN** 编译/校验 MUST fail-fast
- **AND** 错误信息 MUST 指向 `resources.books.report.path`

#### Scenario: xlsx_file relative path is resolved against the YAML directory
- **GIVEN** demand YAML 位于 `/a/b/report.demand.yaml`
- **AND** `resources.books.report.kind=xlsx_file`
- **AND** `resources.books.report.path=./out`
- **WHEN** 系统解析该 book 的输出 root
- **THEN** 解析结果 MUST 等价于 `/a/b/out`(经 `resolve` 归一化)

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
- `export_xlsx.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2）
- `export_xlsx.allow_formulas` MUST 为 bool(默认 `false`)
- 系统 MUST 基于 `book_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/books/<book_id>.xlsx`

legacy `export_xlsx.write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示。

#### Scenario: xlsx_memory budget is required
- **GIVEN** `resources.books.report.kind=xlsx_memory`
- **WHEN** `resources.books.report.budget` 缺失
- **THEN** 编译/校验 MUST fail-fast
- **AND** 错误信息 MUST 指向 `resources.books.report.budget`

#### Scenario: xlsx_memory export_xlsx root can be injected via init_vars
- **GIVEN** `resources.books.report.kind=xlsx_memory`
- **AND** `resources.books.report.export_xlsx.path={$init_var: out_root}`
- **WHEN** 调用方提供 `init_vars={\"out_root\": \"./out\"}`
- **THEN** 编译期解析 MUST 成功

## REMOVED Requirements

### Requirement: workflow book publish MUST enforce write_lock at final_path

**Reason**：在版本化输出（D-2）下，workflow 的 book publish 不再写入共享最终路径；每次运行写入独立版本目录，因此不需要基于 `<final_path>.scalim.lock` 的跨进程互斥。继续保留该配置会引入目录污染与服务端锁冲突风险。

**Migration**：

- 删除 `resources.books.<id>.write_lock` 与 `resources.books.<id>.export_xlsx.write_lock` 配置。
- 通过 `<root>/manifest/latest.json` 或指定 `<root>/versions/<version_id>/...` 读取产物。

#### Scenario: legacy write_lock publish configuration is rejected with a migration hint
- **GIVEN** workflow YAML 仍声明 `workflow.resources.books.report.write_lock=true`
- **WHEN** 系统执行 validate/compile
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示使用版本化输出（manifest/latest.json）替代 write_lock

### Requirement: write_lock=false MUST NOT introduce lock conflicts

**Reason**：该要求基于“lockfile 存在但未启用 write_lock”的历史实现细节；在版本化输出（D-2）下不再产生 `<final_path>.scalim.lock`，因此不再需要定义“write_lock=false 的锁冲突语义”。

**Migration**：

- 不再依赖 lockfile；改为版本化输出目录隔离并发写入。

#### Scenario: publish without write_lock does not create any lockfile artifacts
- **WHEN** workflow 运行并成功发布 book 输出
- **THEN** 系统 MUST NOT 创建任何 `<final_path>.scalim.lock` 形式的锁文件

