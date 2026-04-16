## 背景

workflow DAG 在业务侧常以“阶段(stage)”理解：同一阶段内并行、阶段之间存在显式屏障。当前实现采用 **pipeline** 语义：节点一旦就绪(ready)就会被调度执行，因此会出现“上一阶段尚未全部完成，下一阶段部分节点已开始”的执行形态，降低可预期性与排障效率。

本变更引入一个新的 scheduling preset：在保持默认 pipeline 行为不变的前提下，新增 **stage_barrier** 模式，使调度以“阶段屏障”推进。

当前相关实现要点（用于定位实现边界）：

- workflow runtime policy 已迁出 YAML，调用方通过 `run_workflow(..., workflow_runtime_options=WorkflowRuntimeOptions(...))` 提供执行策略。
- `WorkflowRuntimeOptions` 已包含 `scheduler` 字段；本变更将扩展编译期/运行期校验，使其接受 `PipelineSchedulerOptions` 与 `StageBarrierSchedulerOptions`（`src/scalim/dsl/yaml_dsl/workflow_compile.py`）。
- 执行阶段的调度循环位于 `WorkflowRunController.submit_ready_nodes()`（`src/scalim/workflow/execute_controller.py`），当前仅依据 “ready queue + max_concurrency” 做 pipeline 调度。
- workflow viz 快照已基于 DAG `deps` 推导节点层级(`level`/`wf stage`)（`src/scalim/ob/presets/viz/workflow.py`），可复用为 stage 归因/分组的基础。

约束：

- `src/scalim/` 运行时必须兼容 Python 3.6。
- 文档治理：禁止手改任何 `*.gen.*` 生成物与 `BEGIN/END AUTOGEN` 注入块；更新文档需走 SSOT + 生成入口。

## 目标 / 非目标

**目标：**

- 新增 `StageBarrierSchedulerOptions` preset，并使 `WorkflowRuntimeOptions.scheduler` 支持 `pipeline` / `stage_barrier` 两种模式（typed dataclass 作为策略对象）。
- stage_barrier 语义：**仅当当前 stage 内所有节点到达终态（成功/失败/取消）后，才允许下一 stage 节点开始**。
- 阶段划分自动推导（用户侧 stage）：
  - demand 节点：`stage(node) = max(stage(dep)) + 1`（无 deps 则为 0）
  - 内部 write nodes：`stage(write_node) = stage(input_demand)`（折叠以贴近用户视角；拓扑层级仍保留用于诊断/布局）
- 保持确定性：同一 stage 内若多个节点同时就绪，调度必须以稳定规则选择下一个启动节点（沿用既有 `decl_order` 作为稳定裁决规则）。
- 最小可观测性：对外暴露 `schedule_mode` 与 `stage`（用于解释执行顺序与排障）。
- 默认行为不变：未配置 scheduler 时仍为 pipeline。

**非目标：**

- 不引入新的 YAML authoring 字段（仍禁止 `workflow.options`；scheduler 仅通过 runtime entrypoints 配置）。
- 不引入更复杂的调度策略（优先级/抢占/动态资源配额/每阶段独立并发上限等）。
- 不改变既有 failure policy（`all_fail` / `primary_only`）的语义，只在其边界内实现屏障。

## 设计决策

### 1) Scheduler 配置形态：typed preset 对象

- 新增 `StageBarrierSchedulerOptions`（与 `PipelineSchedulerOptions` 对齐的空配置 dataclass），并将其作为 `WorkflowRuntimeOptions.scheduler` 的可选 preset。
- 保持“策略对象而非字符串策略”风格，避免后续扩展时变为大平铺字符串+散字段组合。

### 2) Stage 归因算法：拓扑层级 + 用户侧折叠

- struct level（拓扑层级）基于 workflow IR 的 `deps` 推导，算法为：
  - `level(node) = 0`，当 `deps` 为空
  - `level(node) = max(level(dep)) + 1`，当存在 deps
- 用户侧 stage 与 struct level 对齐，但对内部 write nodes 做折叠：
  - demand 节点：`stage = level`
  - write nodes：`stage(write_node) = stage(input_demand)`
- 环检测：如果出现环(cycle)（理论上应被编译校验拒绝），派生信息计算应有容错回退（保证不会因布局/诊断而崩溃），但调度仍以编译校验为准。

### 3) 调度实现边界：在 WorkflowRunController 侧实现阶段屏障

- stage_barrier 仅改变“何时允许提交(next submit)”这一层的规则；节点 readiness 仍由依赖计数(`remaining_prereqs`)驱动。
- 在 controller 内引入 `stage_by_node_id` + `current_stage` 状态：
  - 仅允许提交 `stage == current_stage` 的 ready 节点（demand 与 write nodes 都受控）。
  - 当 `current_stage` 的所有节点均到达终态（done/failed/cancelled）后，推进到下一 stage（可连续跳过空 stage）。
- 并发约束：`max_concurrency` 仍是全局 worker 上限；stage_barrier 不引入额外的 per-stage 并发配置。

### 4) 可观测性最小扩展：暴露 schedule_mode 与 stage

实现应至少满足以下其一（优先级从高到低）：

1. 在 workflow viz snapshot 的节点数据中提供 `stage` 信息（可复用既有 `level`/`stage_id`），并在 snapshot 的 metadata 中增加 `schedule_mode`。
2. 或在 workflow node start/end/cancelled 事件 payload（或 meta）中增加 `stage` 与 `schedule_mode` 字段。

关键点：对外必须可解释“为什么它先跑/后跑”，且 stage 归因要与调度保持一致。

### 5) 文档/生成边界与漂移门禁（必须在实现前收敛）

- 本变更的 SSOT：
  - 规范：`openspec/specs/**/spec.md`（归档/同步后为主规范）；变更期在 `openspec/changes/c5-workflow-stage-scheduling/specs/**/spec.md` 描述增量。
  - 代码：`src/scalim/**`（Python 3.6 runtime 边界）。
- 生成/注入边界：
  - 禁止手改 `*.gen.*` 与任何 `BEGIN/END AUTOGEN` 注入块。
  - 若需要更新 docs-site 页面或注入块：编辑 SSOT 后运行 `just gen-docs`。
- 漂移门禁 / 验收口径：
  - OpenSpec：实现前后均可运行 `just openspec-check`（sanitize + `openspec validate`）。
  - 代码质量：`just qa`（lint/tests + drift checks）。

## 风险与权衡

- **吞吐 vs 可预期性**：stage_barrier 会减少 pipeline 的重叠执行，可能降低总体吞吐，但换取更强可解释性与更稳定的阶段边界。
- **内部节点导致解释成本**：workflow IR 可能包含内部节点（write nodes 等）；若按拓扑层级直接暴露，stage 数可能比用户心智更多。为降低误解，本变更将 write nodes 的 user-stage 折叠到其输入 demand 的 stage。
- **失败策略交互**：
  - `all_fail` 下出现失败会取消未开始节点，stage_barrier 的后续 stage 可能不再有实际调度意义；
  - `primary_only` 下失败不会中止整个 workflow，stage_barrier 仍需正确推进到后续 stage（并确保依赖失败导致的取消计入终态）。

## 迁移与验收计划

1. 扩展 `WorkflowRuntimeOptions.scheduler` 的 preset：新增 `StageBarrierSchedulerOptions` 并更新 runtime options 校验。
2. 将 scheduler mode 传递到执行层（扩展 IR options 透传），并在 controller 中实现 `current_stage` 屏障逻辑。
3. 增加最小可观测性：viz snapshot / workflow events 暴露 `stage` + `schedule_mode`。
4. 添加/更新单测覆盖：
   - stage_barrier 下“下一 stage 不能在上一 stage 全终态前启动”的时序断言；
   - pipeline 默认行为保持不变的回归断言。
5. 运行 `just qa` 与 `just openspec-check` 作为验收门禁。

## 已决策项（对应此前 Open Questions）

- 内部节点（write nodes）的阶段归因：对外暴露的 `stage` 折叠到其输入 demand 的 `stage`，避免把“内部写入步骤”误解为新的业务阶段；同时保留拓扑层级派生函数用于诊断/布局。
- 事件层暴露策略：同时在两侧提供最小信息
  - workflow node start/end/cancelled 事件 payload 增量增加 `schedule_mode` 与 `stage`
  - workflow viz snapshot 在 `meta.metadata` 增量增加 `schedule_mode`，节点侧复用 `level`/`stage_id` 作为 stage 展示与分组依据
