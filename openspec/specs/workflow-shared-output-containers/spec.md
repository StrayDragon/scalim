# workflow-shared-output-containers Specification

## Purpose
TBD - created by archiving change c30-workflow-shared-output-containers. Update Purpose after archive.
## Requirements
### Requirement: workflow YAML exposes a stable authoring surface for shared resources and write intents
系统 MUST 为共享输出容器提供可实现、可校验的 workflow YAML authoring surface:

- 资源声明:
  - `workflow.resources.workbooks.<workbook_id>.path` MUST 为非空字符串
  - `workflow.resources.csvs.<csv_id>.path` MUST 为非空字符串
- 写入简写（每个 demand run 可声明 0..N 条 write intents）:
  - `workflow.runs[*].writes` MAY 存在且 MUST 为数组；缺省/空数组表示无写入意图
  - `workflow.runs[*].writes[*]` MUST 恰好包含一个 intent key（否则 fail-fast）
  - 每个 intent key MUST 为以下五者之一:
    - `workbook_sheet`
    - `workbook_append`
    - `csv_append`
    - `sheetbook_sheet`（由 `workflow-sheetbook-resources` 定义）
    - `sheetbook_append`（由 `workflow-sheetbook-resources` 定义）
- `writes[*].workbook_sheet` 对象字段 MUST 满足:
  - `workbook`: workbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `on_conflict` MAY 存在且 MUST 为 `error|overwrite|skip` 之一（默认 `error`）
- `writes[*].workbook_append` 对象字段 MUST 满足:
  - `workbook`: workbook resource id
  - `sheet`: sheet 名（非空字符串）
  - `output`: 上游 demand 的 output id
  - `align_by` MAY 存在且 MUST 为 `field_id|header` 之一（默认 `field_id`）
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）
- `writes[*].csv_append` 对象字段 MUST 满足:
  - `csv`: csv resource id
  - `output`: 上游 demand 的 output id
  - `header_policy` MAY 存在且 MUST 为 `once|always|never` 之一（默认 `once`）
  - `on_mismatch` MAY 存在且 MUST 为 `error|warn|skip` 之一（默认 `error`）

#### Scenario: shared-output authoring surface passes schema validation
- **WHEN** workflow YAML 同时包含 `workflow.resources` 与 `workflow.runs[*].writes`
- **THEN** schema-only 校验 MUST 通过

### Requirement: workflow declares shared output resources at workflow scope
系统 MUST 扩展 workflow YAML 语义,允许在 workflow 层声明共享输出资源(例如 workbook/csv),并由 workflow runtime 统一管理其生命周期:
- 资源声明 MUST 位于 workflow scope(例如 `workflow.resources.workbooks` / `workflow.resources.csvs`)
- 每个资源 MUST 具备稳定 id(资源名)与输出路径
- 系统 MUST 静态校验资源声明(例如 id 唯一、路径合法、必填字段齐全)

#### Scenario: shared resource declaration is validated
- **GIVEN** workflow 声明两个同名 workbook 资源
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告资源 id 冲突

### Requirement: shared output is written via explicit workflow write nodes
系统 MUST 将“写入共享资源”的动作建模为 workflow 的显式节点类型,而不是 demand 的隐式后处理:
- 系统 MUST 支持至少两类写入节点:
  - `write_sheet`(写入/覆盖某个 sheet)
  - `append_sheet`(追加写入某个 sheet,具备明确的字段对齐与 header 策略)
- 写入节点 MUST 消费上游 demand 节点的 output artifacts,并写入声明的共享资源
- YAML authoring surface MAY 提供简写,但编译后语义 MUST 等价于显式 write nodes

#### Scenario: write nodes depend on demand outputs
- **GIVEN** write_sheet 节点消费 run A 的 output `detail`
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 run A 成功完成并产生该 output 后才允许 write_sheet 执行

### Requirement: writes to shared resources are deterministic and serialized
系统 MUST 定义确定性写入顺序,且 MUST NOT 依赖并发完成顺序:
- 对同一共享资源的写入 MUST 互斥/串行化
- 写入顺序 MUST 由 workflow YAML 中 write intents 的声明顺序决定（以 runs 列表顺序为一级 SSOT,以 `writes` 列表顺序为二级 SSOT）,不得依赖线程调度或完成时序

#### Scenario: writes to a shared workbook are deterministic
- **GIVEN** 两个 runs 各自声明多条 `writes`,并写入同一个共享 workbook 的不同 sheet
- **WHEN** workflow 在并发模式下执行多次
- **THEN** 对共享资源的写入顺序 MUST 可复现,且结果 MUST 等价

### Requirement: append/merge semantics are explicit and verifiable
当多个节点写入同一个 sheet 或以 append 方式合并时,系统 MUST 定义明确且可测试的合并语义:
- 字段对齐策略 MUST 明确(例如按 field_id 对齐/按 header 对齐/严格相等)
- header 输出策略 MUST 明确(例如仅一次/每段/禁用)
- 当字段不匹配或冲突时,系统 MUST 提供明确策略并可配置(`error|warn|skip`)

#### Scenario: field alignment policy is enforced
- **GIVEN** append_sheet 声明按 field_id 对齐且策略为严格相等
- **WHEN** 两段输出字段集合不一致
- **THEN** 系统 MUST fail-fast 并报告差异摘要

### Requirement: shared resources commit atomically at workflow end
系统 MUST 定义共享资源的落盘/提交语义,避免“部分写入但语义不清”的灰区:
- 共享资源 MUST 在 workflow 成功结束后统一 commit,并以原子方式落盘(只保存一次/原子替换)
- 当 workflow 失败时,系统 MUST discard 未提交的共享资源（v0 不支持 partial commit）

#### Scenario: failed workflow does not leave partial committed output
- **GIVEN** workflow 包含共享 workbook 且其中部分写入节点已执行
- **AND** 后续节点失败导致 workflow 失败
- **WHEN** workflow 结束
- **THEN** 系统 MUST 不产生“已提交但不完整”的最终 workbook 文件(默认 discard)

### Requirement: shared resource lifecycle MUST be observable
系统 MUST 为共享资源生命周期提供可观测事件/钩子点,以便排障与可视化:
- 系统 MUST 发出以下事件类型:
  - `workflow_resource_create`
  - `workflow_resource_write`
  - `workflow_resource_commit`
  - `workflow_resource_discard`
- 事件 MUST 复用 workflow 归因字段(例如 `workflow_exec_id` / `workflow_node_id`)

#### Scenario: resource lifecycle events are joinable
- **GIVEN** workflow 声明共享 workbook 资源并执行写入
- **WHEN** workflow 成功 commit 或失败 discard 该资源
- **THEN** observer MUST 能观测到对应的 commit/discard 事件
- **AND** 这些事件 MUST 携带 `workflow_exec_id` 以 join 回同一次 workflow 执行

