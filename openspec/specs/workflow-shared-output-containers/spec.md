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
- 写入节点 MUST 消费上游 demand 节点的 output artifacts；该 artifact 可以是文件路径 output，也可以是 workflow-managed 的内存 CSV artifact（`InMemoryCsv`）
- YAML authoring surface MAY 提供简写,但编译后语义 MUST 等价于显式 write nodes
- 当写入节点消费的是 workflow-managed 内存 CSV artifact 时，消费完成后系统 MUST 参与该 artifact 的最终消费者释放流程

#### Scenario: write nodes depend on demand outputs
- **GIVEN** write_sheet 节点消费 run A 的 output `detail`
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 run A 成功完成并产生该 output 后才允许 write_sheet 执行

#### Scenario: write nodes can consume in-memory workflow-managed outputs
- **GIVEN** write_sheet 节点消费 run A 的 pathless CSV output `detail`
- **AND** `detail` 被 workflow 托管为内存 CSV artifact
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 run A 成功完成并发布该 artifact 后允许 write_sheet 执行
- **AND** write_sheet MUST 无需依赖临时 CSV 文件路径即可完成写入

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

### Requirement: shared resource plan creation MUST be atomic and joinable within a workflow exec
当 workflow 并发执行多个 nodes 且多个 write intents 引用同一个共享资源（`csv` 或 `workbook`）时,系统 MUST 确保该资源在一次 workflow 执行内仅创建一个 plan,并允许并发写入方 join 到同一 plan：

- 对同一 `resource_id` 的 “get-or-create” MUST 原子（并发首次命中不得产生多个 plan）。
- `csv/workbook` 的写锁获取 MUST 与该 plan 绑定且在一次 workflow 执行内只发生一次；同一 workflow 内的其它并发写入 MUST join 而不是被误判为并发写者。
- 最终 commit MUST 包含所有写入方产生的写入意图（不得丢写）。

#### Scenario: concurrent writes to a shared workbook join a single plan
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 与 B 都写入同一个共享 workbook 资源 `report` 的不同 sheets
- **WHEN** 多次执行该 workflow
- **THEN** 系统 MUST 不得因“重复获取写锁”而 fail-fast
- **AND** 最终导出的 workbook MUST 同时包含 A 与 B 的写入结果

#### Scenario: concurrent appends to a shared csv join a single plan
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 与 B 都 append 写入同一个共享 csv 资源 `detail`
- **WHEN** 多次执行该 workflow
- **THEN** 系统 MUST 不得因“并发首次命中同一 csv”而 fail-fast
- **AND** 最终落盘的 csv MUST 包含两段 append 的写入结果（顺序由声明顺序决定）

### Requirement: joinable get-or-create 的等待诊断
系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 wait diagnostics,使 waiter 等待过程可观测且可定位.

约束:
- 诊断配置 MUST 包含 `warn_after_s`(首次告警阈值)和可选的 `repeat_every_s`(重复告警间隔)
- 告警 MUST 包含: `resource_id`、`resource_type`、owner 线程标识、waiter 线程标识、已等待时长
- 告警 MUST 走 instrumentation event 或 warning logger,不得污染正常输出
- 默认行为 MUST 为禁用(避免行为变化)

#### Scenario: waiter 等待超过阈值时产生诊断告警
- **GIVEN** wait diagnostics 启用且 `warn_after_s=5.0`
- **WHEN** waiter 等待 owner 创建资源超过 5 秒
- **THEN** 系统 MUST 发出包含 resource_id/owner_thread/waiter_thread/wait_s 的告警

#### Scenario: 重复告警
- **GIVEN** wait diagnostics 启用且 `repeat_every_s=10.0`
- **WHEN** waiter 持续等待
- **THEN** 系统 MUST 每隔 `repeat_every_s` 重复告警(首次在 `warn_after_s` 时)

### Requirement: joinable get-or-create 的可选超时
系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 max wait / fail-fast 能力.

约束:
- 超时后 MUST 以 `WorkflowWriteError` 失败,错误消息包含 resource_id、owner 线程标识、已等待时长
- 默认策略 MUST 为"仅告警不超时"(避免行为变化)
- 超时值 MUST 可配置(建议通过 workflow-level 配置或环境变量)

#### Scenario: owner 卡死导致 waiter 超时
- **GIVEN** max_wait_s 配置为 60 秒
- **WHEN** owner 线程创建资源超过 60 秒未完成
- **THEN** waiter MUST 以包含诊断信息的 `WorkflowWriteError` 失败

### Requirement: commit_all/discard_all 与 inflight 并发交错语义
系统 MUST 在 `commit_all()`/`discard_all()` 执行时显式处理与 inflight 创建的并发交错,并采用 **drain** 策略:

- commit/discard 在开始前 MUST 等待所有 inflight 创建完成,保证不会"漏 commit / 漏 discard"

约束:
- drain 等待 MUST 复用 wait diagnostics(含 warn-after/timeout)

#### Scenario: commit_all 与 inflight 创建并发时 drain
- **GIVEN** 采用 drain 策略
- **WHEN** 某线程正在 inflight 创建资源,另一线程调用 `commit_all()`
- **THEN** `commit_all()` MUST 等待 inflight 创建完成后再 commit 所有资源

### Requirement: workflow workbook exports MUST escape Excel formulas by default
当 workflow 通过共享 `workbook` 资源导出 `.xlsx` 时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

转义规则 MUST 满足：
- 仅对 `str` 生效（其它类型保持原样）。
- 若原始字符串以 `'` 开头,MUST 保持不变（避免重复转义）。
- 对 `value.lstrip()` 的首字符,若属于 `{ '=', '+', '-', '@' }`,MUST 在**原始值**前追加 `'`。
- 其它字符串 MUST 保持不变。
- 该规则 MUST 同时作用于表头行与数据行。

允许公式（可信输入显式放宽）：
- 若 `workflow.resources.workbooks.<workbook_id>.allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: formula-like values are escaped by default
- **GIVEN** workflow 声明 workbook 资源 `report` 且未显式设置 `workflow.resources.workbooks.report.allow_formulas`
- **WHEN** 某个 write intent 将字符串 `\"=1+1\"` 与 `\"  +SUM(A1:A2)\"` 写入该 workbook
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 分别为 `\"'=1+1\"` 与 `\"'  +SUM(A1:A2)\"`

#### Scenario: allow_formulas opt-out preserves raw strings
- **GIVEN** workflow 声明 `workflow.resources.workbooks.report.allow_formulas=true`
- **WHEN** 某个 write intent 将字符串 `\"=1+1\"` 写入该 workbook
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 仍为 `\"=1+1\"`

### Requirement: workflow workbook resource authoring surface MUST support allow_formulas
系统 MUST 支持 workflow YAML 的 workbook 资源声明包含可选字段 `workflow.resources.workbooks.<workbook_id>.allow_formulas`：

- 该字段 MUST 为 bool
- 缺省时 MUST 等价于 `false`

#### Scenario: workbook allow_formulas passes schema validation
- **WHEN** workflow YAML 声明 `workflow.resources.workbooks.report.allow_formulas=false`
- **THEN** schema-only 校验 MUST 通过
