# workflow-sheetbook-resources Specification

**状态: ✅ 已实现**

## Purpose
定义 workflow YAML 的 sheetbook 资源(authoring surface)、预算护栏与写入 intent(`writes[*].sheetbook_*`)契约,并要求写入行为确定性、冲突安全、可观测且可原子导出为最终 xlsx,同时提供内置 loader 供下游节点读取 sheet rows.
## Requirements
### Requirement: workflow YAML exposes a stable authoring surface for sheetbooks
系统 MUST 为 sheetbook 资源提供可实现、可校验的 workflow YAML authoring surface:

- 资源声明:
  - `workflow.resources.sheetbooks.<sheetbook_id>.budget.max_sheets` MUST 为正整数
  - `workflow.resources.sheetbooks.<sheetbook_id>.budget.max_total_cells` MUST 为正整数
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.path` MAY 存在且 MUST 为非空字符串
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.write_lock` MAY 存在且 MUST 为 bool
- 写入简写（每个 demand run 可声明 0..N 条 write intents）:
  - `workflow.runs[*].writes` MAY 存在且 MUST 为数组
  - `workflow.runs[*].writes[*]` MUST 恰好包含一个 intent key
  - 对 sheetbook 相关 intent:
    - `workflow.runs[*].writes[*].sheetbook_sheet` MAY 存在（写入/覆盖 sheet）
    - `workflow.runs[*].writes[*].sheetbook_append` MAY 存在（追加写入 sheet）
- `writes[*].sheetbook_sheet` 对象字段 MUST 满足:
  - `sheetbook`: sheetbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `on_conflict` MAY 存在且 MUST 为 `error|overwrite|skip` 之一（默认 `error`）
- `writes[*].sheetbook_append` 对象字段 MUST 满足:
  - `sheetbook`: sheetbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `align_by` MAY 存在且 MUST 为 `field_id|header` 之一（默认 `field_id`）
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）

#### Scenario: sheetbook authoring surface passes schema validation
- **WHEN** workflow YAML 包含 `workflow.resources.sheetbooks` 与 `workflow.runs[*].writes[*].sheetbook_sheet`
- **THEN** schema-only 校验 MUST 通过

### Requirement: workflow MUST support in-memory sheetbook resources
系统 MUST 支持在 workflow scope 声明 `sheetbook`（内存工作簿）资源,用于在同一次 workflow 执行内跨 nodes 共享表格集合:

- `sheetbook` 资源 MUST 仅存在于内存中,不要求具备输出路径
- `sheetbook` 资源 MUST 具备稳定 id,可被 nodes 引用
- 系统 MUST 为 `sheetbook` 提供预算护栏配置入口(SSOT: max_sheets/max_total_cells),并在超限时 fail-fast

#### Scenario: sheetbook resources pass schema validation
- **WHEN** workflow 声明 `sheetbook` 资源并被 schema-only 校验
- **THEN** 校验 MUST 通过

### Requirement: writes to a sheetbook MUST be deterministic and conflict-safe
系统 MUST 支持将多个上游节点的输出写入同一个 sheetbook,并保证写入行为确定性与冲突安全:

- 对同一个 sheetbook 的写入 MUST 互斥/串行化,不得依赖并发完成时序
- 写入顺序 MUST 由 workflow YAML 的声明顺序决定（以 runs 列表顺序为一级 SSOT,以 `writes` 列表顺序为二级 SSOT）
- 当发生 sheet 名冲突/写入重复/字段对齐冲突时,系统 MUST fail-fast 并提供可诊断摘要

#### Scenario: deterministic order does not depend on completion timing
- **GIVEN** 两个并发执行的上游节点都写入同一个 sheetbook 的不同 sheet,且每个节点声明多条 `writes`
- **WHEN** 多次执行同一个 workflow
- **THEN** 生成的 sheet 顺序与内容 MUST 可复现

### Requirement: workflow MUST support exporting a sheetbook to an Excel workbook atomically
系统 MUST 支持将 sheetbook 导出为最终的 xlsx 文件,并提供原子落盘语义以避免部分提交:

- 导出 MUST 以临时文件写入并原子替换到目标路径
- 当 workflow 失败时,系统 MUST 不产生“已提交但不完整”的最终 xlsx 文件(统一 discard)
- 若启用写锁,系统 MUST 在导出时使用写锁以防止并发写同一路径

#### Scenario: failed workflow does not commit partial xlsx
- **GIVEN** workflow 生成 sheetbook 且导出目标为 `./out/report.xlsx`
- **AND** 导出前某个下游节点失败导致 workflow 失败
- **WHEN** workflow 结束
- **THEN** 系统 MUST 不生成不完整的 `./out/report.xlsx`(默认 discard)

### Requirement: demand nodes MUST be able to consume sheetbook sheet rows via a built-in loader
系统 MUST 提供内置 loader `scalim.workflow.loaders:sheetbook_sheet_rows`,允许下游 demand 将上游 sheetbook 的某个 sheet 作为 rows 输入使用:

- loader MUST 接收 `params.ref` 映射对象,并满足以下结构:
  - `ref.node`（上游 node id）
  - `ref.sheetbook`（sheetbook 资源 id）
  - `ref.sheet`（sheet 名）
- loader MUST 返回可迭代 rows（每行 MUST 为 JSON-like mapping）
- 系统 MUST 强制依赖闭包可见性: 下游 node 仅允许读取其依赖闭包内上游 nodes 的 sheetbook
- 当引用越界或目标 sheet 不存在时,系统 MUST fail-fast 并提供可诊断摘要

#### Scenario: reading a non-dependency sheetbook is rejected
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 的 demand 通过内置 loader 引用 node A 的 sheetbook sheet
- **THEN** 系统 MUST fail-fast 并报告“引用超出 deps 可见范围”

### Requirement: workflow MUST precheck Excel output-path collisions across nodes
当 workflow 并发执行多个 nodes 且存在文件输出时,系统 MUST 在“写入发生前”检测潜在的输出路径冲突,避免依赖运行时写锁导致的不确定失败:

- 若多个 nodes 的 demand 输出将写入同一个 xlsx 路径,系统 MUST fail-fast 并指出冲突 nodes 与路径
- 若路径可在结构编译阶段静态提取,冲突 MUST 在结构编译阶段 fail-fast
- 若路径依赖 `init_vars/$ctx` 等动态渲染,冲突 MUST 在 node 物化编译后、实际写入前 fail-fast
- 若某个 xlsx 路径被 workflow 声明为共享输出资源(例如 `resources.workbooks[*].path` 或 `resources.sheetbooks[*].export_xlsx.path`),系统 MUST 禁止 nodes 直接写该路径（必须通过共享资源 + 写出节点/commit 流程）

#### Scenario: duplicate xlsx output paths are rejected deterministically
- **GIVEN** 两个 nodes 的 demand 都声明输出到同一个 xlsx 路径
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告冲突路径与节点 id

#### Scenario: dynamic init_vars output path participates in collision checks using resolved path
- **GIVEN** workflow 包含两个 runs: A 与 B
- **AND** run A 的 demand 声明 `outputs[0].container.path={$init_var: output_path}`
- **AND** run B 的 demand 声明 `outputs[0].container.path={$init_var: output_path}`
- **AND** workflow 运行时为 A 注入 `init_vars={"output_path": "./out/a.xlsx"}`
- **AND** workflow 运行时为 B 注入 `init_vars={"output_path": "./out/b.xlsx"}`
- **WHEN** workflow 执行并物化编译每个 node
- **THEN** 系统 MUST NOT 将 `{$init_var: output_path}` 的字面结构字符串化后参与 collision 判断
- **AND** 系统 MUST 以最终解析后的绝对路径（`./out/a.xlsx` 与 `./out/b.xlsx`）作为判定基准

#### Scenario: dynamic ctx-derived output path fails-fast before write
- **GIVEN** run B 的 demand 输出路径由 `workflow.runs[B].init_vars` 使用 `$ctx` 引用 run A 的运行摘要并拼装得到
- **WHEN** run B 的 node 被物化编译且其 `init_vars` 已完成 `$ctx` 渲染
- **THEN** 系统 MUST 在实际写入发生前对渲染后的最终路径执行 reserved/collision 检查
- **AND** 若触发冲突,系统 MUST fail-fast 并报告最终 path 与冲突 nodes

#### Scenario: reserved xlsx paths are checked using resolved dynamic path
- **GIVEN** workflow 声明 `workflow.resources.sheetbooks.report.export_xlsx.path=./out/report.xlsx`
- **AND** 某个 run 的 demand 声明 `outputs[0].container.path={$init_var: output_path}`
- **AND** 该 run 的 `init_vars={"output_path": "./out/report.xlsx"}`
- **WHEN** workflow 物化编译该 run 且准备执行写入
- **THEN** 系统 MUST fail-fast 并报告该路径被 workflow shared resources 保留（必须使用 resources + write nodes）

### Requirement: sheetbook lifecycle MUST be observable and joinable
系统 MUST 为 sheetbook 资源的关键生命周期动作提供可观测事件/钩子点,以便排障与可视化:

- 系统 MUST 发出以下事件类型:
  - `workflow_resource_create`
  - `workflow_resource_write`
  - `workflow_resource_commit`（对 sheetbook 表示导出/提交）
  - `workflow_resource_discard`
- 事件 MUST 复用 workflow 归因字段(例如 `workflow_exec_id` / `workflow_node_id`)

#### Scenario: sheetbook export emits joinable events
- **GIVEN** workflow 创建并写入一个 sheetbook,并成功导出为 xlsx
- **WHEN** observer 订阅 workflow-level 事件流
- **THEN** observer MUST 能观测到 sheetbook export 事件
- **AND** 该事件 MUST 携带 `workflow_exec_id` 以 join 回同一次 workflow 执行

### Requirement: sheetbook plan creation MUST be atomic within a workflow exec
当 workflow 并发执行多个 nodes 且多个 write intents 引用同一个 `sheetbook` 资源时,系统 MUST 确保该 sheetbook 在一次 workflow 执行内仅创建一个 plan,并且不得发生并发覆盖导致的丢写：

- 对同一 `sheetbook_id` 的 “get-or-create” MUST 原子（并发首次命中不得产生多个 plan）。
- 并发写入 MUST 汇聚到同一个 plan,最终导出/commit MUST 包含所有写入结果（不得丢写）。

#### Scenario: concurrent writes to a sheetbook do not lose data
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 写入 sheetbook `report` 的 sheet `s1`
- **AND** B 写入 sheetbook `report` 的 sheet `s2`
- **WHEN** 多次执行该 workflow
- **THEN** 导出的 sheetbook（内存或 xlsx）MUST 同时包含 `s1` 与 `s2` 的内容

### Requirement: sheetbook xlsx export MUST escape Excel formulas by default
当 workflow 声明 `sheetbook` 资源并配置 `workflow.resources.sheetbooks.<id>.export_xlsx.path` 导出 `.xlsx` 时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

允许公式（可信输入显式放宽）：
- 若 `workflow.resources.sheetbooks.<id>.export_xlsx.allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: sheetbook export escapes formula-like values by default
- **GIVEN** workflow 声明 `sheetbook` 资源并启用 `export_xlsx.path`,且未显式设置 `export_xlsx.allow_formulas`
- **WHEN** 某个 sheet 被写入包含 `\"@HYPERLINK(\\\"http://example\\\",\\\"x\\\")\"` 的字符串 cell 值
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 以 `'` 前缀转义（例如 `\"'@HYPERLINK(\\\"http://example\\\",\\\"x\\\")\"`）

#### Scenario: sheetbook export allow_formulas opt-out preserves raw strings
- **GIVEN** workflow 声明 `workflow.resources.sheetbooks.report.export_xlsx.allow_formulas=true`
- **WHEN** 写入字符串 `\"-1+2\"` 到导出的 sheetbook
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 仍为 `\"-1+2\"`

### Requirement: sheetbook export_xlsx authoring surface MUST support allow_formulas
系统 MUST 支持 workflow YAML 的 sheetbook 导出配置 `workflow.resources.sheetbooks.<id>.export_xlsx` 包含可选字段 `allow_formulas`：

- `workflow.resources.sheetbooks.<id>.export_xlsx.allow_formulas` MUST 为 bool
- 缺省时 MUST 等价于 `false`

#### Scenario: sheetbook export_xlsx allow_formulas passes schema validation
- **WHEN** workflow YAML 声明 `workflow.resources.sheetbooks.report.export_xlsx.allow_formulas=false`
- **THEN** schema-only 校验 MUST 通过
