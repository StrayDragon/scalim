## ADDED Requirements

### Requirement: workflow YAML exposes a stable authoring surface for sheetbooks
系统 MUST 为 sheetbook 资源提供可实现、可校验的 workflow YAML authoring surface:

- 资源声明:
  - `workflow.resources.sheetbooks.<sheetbook_id>.budget.max_sheets` MUST 为正整数
  - `workflow.resources.sheetbooks.<sheetbook_id>.budget.max_total_cells` MUST 为正整数
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.path` MAY 存在且 MUST 为非空字符串
  - `workflow.resources.sheetbooks.<sheetbook_id>.export_xlsx.write_lock` MAY 存在且 MUST 为 bool
- 写入简写（每个 demand run 最多声明一个 write intent）:
  - `workflow.runs[*].write_to.sheetbook_sheet` MAY 存在（写入/覆盖 sheet）
  - `workflow.runs[*].write_to.sheetbook_append` MAY 存在（追加写入 sheet）
  - 同一个 run MUST NOT 同时声明 `sheetbook_sheet` 与 `sheetbook_append`
  - 同一个 run MUST NOT 同时声明 sheetbook write intent 与 workbook/csv write intent（write_to 下最多一个 intent key）
- `write_to.sheetbook_sheet` 对象字段 MUST 满足:
  - `sheetbook`: sheetbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `on_conflict` MAY 存在且 MUST 为 `error|overwrite|skip` 之一（默认 `error`）
- `write_to.sheetbook_append` 对象字段 MUST 满足:
  - `sheetbook`: sheetbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `align_by` MAY 存在且 MUST 为 `field_id|header` 之一（默认 `field_id`）
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）

#### Scenario: sheetbook authoring surface passes schema validation
- **WHEN** workflow YAML 包含 `workflow.resources.sheetbooks` 与 `workflow.runs[*].write_to.sheetbook_sheet`
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
- 写入顺序 MUST 由 workflow YAML 的 runs 列表顺序决定（以 write intent 的声明顺序为 SSOT）
- 当发生 sheet 名冲突/写入重复/字段对齐冲突时,系统 MUST fail-fast 并提供可诊断摘要

#### Scenario: deterministic order does not depend on completion timing
- **GIVEN** 两个并发执行的上游节点都写入同一个 sheetbook 的不同 sheet
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
系统 MUST 提供内置 loader `scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows`,允许下游 demand 将上游 sheetbook 的某个 sheet 作为 rows 输入使用:

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
