# workflow-shared-output-containers Specification

## Purpose
TBD - created by archiving change c30-workflow-shared-output-containers. Update Purpose after archive.
## Requirements
### Requirement: workflow YAML exposes a stable authoring surface for shared resources and write intents
系统 MUST 为共享输出容器提供可实现、可校验的 workflow YAML authoring surface,并将“写入意图”从 workflow `writes` 收敛为 demand outputs 的 IO 绑定(由 workflow 编译期推导写入节点):

- 资源声明:
  - `workflow.resources.books.<book_id>` MUST 为 mapping 且 MUST 满足 `yaml-dsl-books-resources` 对 book 的约束
- 写入意图:
  - workflow YAML MUST NOT 再暴露已移除的 workflow-level 写入 intents authoring surface
  - 系统 MUST 从每个 run 引用的 demand YAML 中读取 `outputs[*].to` / `outputs[*].write` 推导等价的写入节点集合

迁移约束(破坏性变更):

- legacy workflow resource groups(workbooks/csvs/sheetbooks) MUST 被拒绝并给出迁移提示(迁移到 `workflow.resources.books`)
- 已移除的 workflow-level 写入 intents MUST 被拒绝并给出迁移提示(迁移到 demand outputs 的 `to/write` 绑定)

#### Scenario: shared-output authoring surface passes schema validation
- **WHEN** workflow YAML 包含 `workflow.resources.books` 且不包含已移除的 workflow-level 写入 intents
- **THEN** schema-only 校验 MUST 通过

### Requirement: workflow declares shared output resources at workflow scope
系统 MUST 扩展 workflow YAML 语义,允许在 workflow 层声明共享输出资源(books),并由 workflow runtime 统一管理其生命周期:

- 资源声明 MUST 位于 workflow scope: `workflow.resources.books`
- 每个资源 MUST 具备稳定 id(资源名)与 kind 对应的必要配置(例如 path/budget/export)
- 系统 MUST 静态校验资源声明(例如 id 唯一、必填字段齐全、预算为正整数等)

#### Scenario: shared resource declaration is validated
- **GIVEN** workflow 声明两个同名 book 资源
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告资源 id 冲突

### Requirement: shared output is written via explicit workflow write nodes
系统 MUST 将“写入共享 book 资源”的动作建模为 workflow 的显式节点类型,而不是 demand 的隐式后处理:

- 系统 MUST 支持至少两类写入节点语义:
  - `write_sheet`(写入/覆盖某个 sheet; 对应 `mode=sheet`)
  - `append_sheet`(追加写入某个 sheet; 对应 `mode=append`,具备字段对齐与 header 策略)
- workflow YAML authoring surface 不再手写 write intents,但编译后语义 MUST 等价于显式 write nodes
- 写入节点 MUST 消费上游 demand 节点的 output artifacts；该 artifact 可以是文件路径 output,也可以是 workflow-managed 的内存表格 artifact(例如 `InMemoryRows` 或等价结构)
- 当写入节点消费的是 workflow-managed 内存 artifact 时,消费完成后系统 MUST 参与该 artifact 的最终消费者释放流程

#### Scenario: write nodes depend on demand outputs
- **GIVEN** write_sheet 节点消费 run A 的 output `detail`
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 run A 成功完成并产生该 output 后才允许 write_sheet 执行

#### Scenario: write nodes can consume workflow-managed in-memory artifacts
- **GIVEN** write_sheet 节点消费 run A 的 output `detail`
- **AND** `detail` 在 workflow 托管场景下被物化为内存 artifact(实现细节,不暴露为 DSL 形态)
- **WHEN** workflow 执行
- **THEN** write_sheet MUST 无需依赖临时 CSV 文件路径即可完成写入

### Requirement: writes to shared resources are deterministic and serialized
系统 MUST 定义确定性写入顺序,且 MUST NOT 依赖并发完成顺序:

- 对同一共享 book 资源的写入 MUST 互斥/串行化
- 写入顺序 MUST 由声明顺序决定:
  - 以 workflow YAML `runs` 列表顺序为一级 SSOT
  - 以每个 demand YAML 的 `outputs` 列表顺序为二级 SSOT

#### Scenario: writes to a shared book are deterministic
- **GIVEN** 两个 runs 都绑定到同一个共享 book 的不同 sheets
- **WHEN** workflow 在并发模式下执行多次
- **THEN** 对共享资源的写入顺序 MUST 可复现,且结果 MUST 等价

### Requirement: append/merge semantics are explicit and verifiable
当多个节点写入同一个 sheet 或以 append 方式合并时,系统 MUST 定义明确且可测试的合并语义:

- 字段对齐策略 MUST 明确(例如按 field_id 对齐/按 header 对齐)
- header 输出策略 MUST 明确(例如仅一次/每段/禁用)
- 当字段不匹配或冲突时,系统 MUST 提供明确策略并可配置(`error|warn|skip`)

该策略的 authoring surface MUST 以 `resources.books.*.write_defaults` 与 `outputs[*].write` 表达(SSOT),不得再通过 workflow `writes` 表达。

#### Scenario: field alignment policy is enforced
- **GIVEN** append_sheet 声明按 field_id 对齐且策略为严格相等
- **WHEN** 两段输出字段集合不一致
- **THEN** 系统 MUST fail-fast 并报告差异摘要

### Requirement: shared resources commit atomically at workflow end
系统 MUST 定义共享资源的落盘/提交语义,避免“部分写入但语义不清”的灰区:

- 共享资源 MUST 在 workflow 成功结束后统一 commit,并以原子方式落盘(只保存一次/原子替换)
- 当 workflow 失败时,系统 MUST discard 未提交的共享资源（v0 不支持 partial commit）

#### Scenario: failed workflow does not leave partial committed output
- **GIVEN** workflow 包含共享 book 且其中部分写入节点已执行
- **AND** 后续节点失败导致 workflow 失败
- **WHEN** workflow 结束
- **THEN** 系统 MUST 不产生“已提交但不完整”的最终 xlsx 文件(默认 discard)

### Requirement: shared resource lifecycle MUST be observable
系统 MUST 为共享资源生命周期提供可观测事件/钩子点,以便排障与可视化:

- 系统 MUST 发出以下事件类型:
  - `workflow_resource_create`
  - `workflow_resource_write`
  - `workflow_resource_commit`
  - `workflow_resource_discard`
- 事件 MUST 复用 workflow 归因字段(例如 `workflow_exec_id` / `workflow_node_id`)

#### Scenario: resource lifecycle events are joinable
- **GIVEN** workflow 声明共享 book 资源并执行写入
- **WHEN** workflow 成功 commit 或失败 discard 该资源
- **THEN** observer MUST 能观测到对应的 commit/discard 事件
- **AND** 这些事件 MUST 携带 `workflow_exec_id` 以 join 回同一次 workflow 执行

### Requirement: shared resource plan creation MUST be atomic and joinable within a workflow exec
当 workflow 并发执行多个 nodes 且多个写入节点引用同一个共享 book 资源时,系统 MUST 确保该资源在一次 workflow 执行内仅创建一个 plan,并允许并发写入方 join 到同一 plan：

- 对同一 `resource_id` 的 “get-or-create” MUST 原子（并发首次命中不得产生多个 plan）。
- 该资源的写锁获取 MUST 与该 plan 绑定且在一次 workflow 执行内只发生一次；同一 workflow 内的其它并发写入 MUST join 而不是被误判为并发写者。
- 最终 commit MUST 包含所有写入方产生的写入意图（不得丢写）。

#### Scenario: concurrent writes to a shared book join a single plan
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 与 B 都写入同一个共享 book 资源 `report` 的不同 sheets
- **WHEN** 多次执行该 workflow
- **THEN** 系统 MUST 不得因“重复获取写锁”而 fail-fast
- **AND** 最终导出的 xlsx MUST 同时包含 A 与 B 的写入结果

### Requirement: joinable get-or-create 的等待诊断
系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 wait diagnostics,使 waiter 等待过程可观测且可定位.

约束:

- 诊断配置 MUST 包含 `warn_after_s`(首次告警阈值)和可选的 `repeat_every_s`(重复告警间隔)
- 告警 MUST 包含: `resource_id`、owner 线程标识、waiter 线程标识、已等待时长
- 告警 MUST 走 instrumentation event 或 warning logger,不得污染正常输出
- 默认行为 MUST 为禁用(避免行为变化)

#### Scenario: waiter 等待超过阈值时产生诊断告警
- **GIVEN** wait diagnostics 启用且 `warn_after_s=5.0`
- **WHEN** waiter 等待 owner 创建资源超过 5 秒
- **THEN** 系统 MUST 发出包含 resource_id/owner_thread/waiter_thread/wait_s 的告警

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
当 workflow 通过共享 `books.kind=xlsx_file` 或 `books.kind=xlsx_memory.export_xlsx` 导出 `.xlsx` 时,系统 MUST 默认对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

允许公式（可信输入显式放宽）：

- 若 effective book 配置 `allow_formulas=true`,系统 MUST 禁用上述转义并保留原始字符串。

#### Scenario: formula-like values are escaped by default
- **GIVEN** workflow 声明 book 资源 `report` 且未显式设置 `allow_formulas`
- **WHEN** 某个写入节点将字符串 `\"=1+1\"` 写入该 book
- **THEN** 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`

### Requirement: workflow workbook resource authoring surface MUST support allow_formulas
系统 MUST 支持 workflow YAML 的 book 资源声明包含可选字段 `workflow.resources.books.<book_id>.allow_formulas`：

- 该字段 MUST 为 bool
- 缺省时 MUST 等价于 `false`

#### Scenario: book allow_formulas passes schema validation
- **WHEN** workflow YAML 声明 `workflow.resources.books.report.allow_formulas=false`
- **THEN** schema-only 校验 MUST 通过

### Requirement: workflow MUST precheck Excel output-path collisions across books deterministically
当 workflow 声明多个 `xlsx` 导出路径时,系统 MUST 在“写入发生前”检测潜在的路径冲突,并采用确定性规则 fail-fast:

- 若两个 book 的 effective 导出路径相同(同一路径),系统 MUST 拒绝执行并报告冲突的 book ids 与 path
- 路径判定 MUST 基于 `expanduser + resolve(strict=False)` 的归一化绝对路径

动态路径约束:

- 若 book path 由 `{$init_var: ...}` 注入,系统 MUST 使用渲染后的最终路径参与冲突判断
- 对依赖 `$ctx` 的注入(compile-on-ready) MUST 在该节点物化编译后,仍在实际写入前做最终冲突预检查

#### Scenario: duplicate xlsx export paths are rejected deterministically
- **GIVEN** workflow 声明两个 book: `a` 与 `b`
- **AND** `workflow.resources.books.a.kind=xlsx_file`
- **AND** `workflow.resources.books.b.kind=xlsx_file`
- **AND** `workflow.resources.books.a.path=./out/report.xlsx`
- **AND** `workflow.resources.books.b.path=./out/report.xlsx`
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告冲突路径与 book ids

### Requirement: commit order MUST NOT depend on thread scheduling

当 workflow 在并发模式执行时,系统 MUST 禁止将共享资源（csv/workbook/sheetbook）的最终写入顺序绑定到线程调度或节点完成时序.

系统 MUST 为每条写入意图记录稳定的 `decl_order`（声明顺序序号）,并在 commit 阶段按 `decl_order` 稳定排序后写出.

#### Scenario: concurrent appends preserve declaration order
- **GIVEN** 两个并发 runs 对同一共享 csv 资源 append 写入
- **WHEN** workflow 在并发模式下重复执行多次
- **THEN** 最终落盘 csv 的段顺序 MUST 始终与 YAML 声明顺序一致

### Requirement: workbook/sheetbook sheet order MUST be stable

系统 MUST 定义 workbook/sheetbook 的 sheet 顺序策略,且不得依赖“并发首次创建时 append”导致的漂移.

#### Scenario: sheet order is stable across concurrent runs
- **WHEN** 并发执行多个写入不同 sheets 的 write intents
- **THEN** 导出的 workbook/sheetbook 内 sheet 顺序 MUST 可复现
