# language: zh-CN
# capability: workflow-stage-scheduling
# purpose: 为 workflow DAG 提供可配置的调度 preset，使调用方可以在保持默认 pipeline 行为不变的前提下，选择严格的 stage barrier（阶段屏障）调度，以提升可预期性、资源规划与可解释性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: workflow-stage-scheduling

  @req:r99 @human
  场景: workflow runtime MUST 支持 scheduler preset（pipeline / stage_barrier）
    - 系统 MUST 通过运行期策略边界（runtime policy boundary）提供 workflow scheduler preset 的选择入口： - 调用方 MUST 能通过 `workflow_runtime_options.scheduler` 选择调度 preset（以 typed dataclass 作为策略对象）。 - 当调用方未显式配置 scheduler 时，系统 MUST 使用 `pipeline` 作为默认 preset。

  @req:r341 @human
  场景: stage_barrier scheduler MUST 强制严格阶段屏障
    - 当调用方选择 `stage_barrier` preset 时，系统 MUST 以“阶段”为屏障推进调度： - 定义 stage（demand 节点）：`stage(node) = max(stage(dep)) + 1`（无 deps 则为 0） - 对内部 write nodes：系统对外暴露的 `stage` MUST 折叠到其输入 demand 的 stage（避免把内部写入步骤误解为新的业务阶段） - 系统 MUST NOT 启动 stage `k+1` 的任一节点，直到 stage `k` 的所有节点均到达终态（成功/失败/取消）

  @req:r463 @human
  场景: stage 推导 MUST 确定且可解释
    - 系统 MUST 基于 workflow DAG 拓扑推导 stage 归因，并保持确定性： - 对同一份 workflow IR（相同的 nodes/deps），`stage_by_node_id` 的结果 MUST 稳定且不依赖并发完成时序 - 当 DAG 编译阶段发现 cycle 时，系统 MUST 快速失败（fail-fast）（stage 推导仅作为可观测性/布局/调度的派生信息）

  @req:r548 @human
  场景: schedule_mode 与 stage MUST 可观测
    - 系统 MUST 对外暴露最小可观测性信息，用于解释执行顺序： - 对每个 workflow node，系统 MUST 能暴露其 `stage` 归因 - 系统 MUST 能暴露本次 workflow 的 `schedule_mode`（`pipeline` 或 `stage_barrier`）
  @req:r99 @human
  场景: pipeline-preset-在-deps-允许时可跨-stage-重叠执行
    - 必须成立：假如 workflow 包含两个 stage 0 节点 `a` 与 `x`（均无 deps），以及一个 stage 1 节点 `b`（`b depends_on [a]`）；当 调用方以 `workflow_runtime_options.scheduler=pipeline` 运行该 workflow；那么 系统 MUST 允许在 `x` 尚未终态时启动 `b`（只要 `a` 已终态且 worker 有空闲）
    假如 workflow 包含两个 stage 0 节点 `a` 与 `x`（均无 deps），以及一个 stage 1 节点 `b`（`b depends_on [a]`）
    当 调用方以 `workflow_runtime_options.scheduler=pipeline` 运行该 workflow
    那么 系统 MUST 允许在 `x` 尚未终态时启动 `b`（只要 `a` 已终态且 worker 有空闲）
  @req:r341 @human
  场景: stage-barrier-必须等当前-stage-全部终态后才可启动下一-stage
    - 必须成立：假如 workflow 包含两个 stage 0 节点 `a` 与 `x`（均无 deps），以及一个 stage 1 节点 `b`（`b depends_on [a]`）；当 调用方以 `workflow_runtime_options.scheduler=stage_barrier` 运行该 workflow；那么 系统 MUST NOT 在 `x` 到达终态前启动 `b`
    假如 workflow 包含两个 stage 0 节点 `a` 与 `x`（均无 deps），以及一个 stage 1 节点 `b`（`b depends_on [a]`）
    当 调用方以 `workflow_runtime_options.scheduler=stage_barrier` 运行该 workflow
    那么 系统 MUST NOT 在 `x` 到达终态前启动 `b`
  @req:r463 @human
  场景: stage-推导与拓扑层级一致-demand-节点
    - 必须成立：假如 workflow DAG 满足 `a -> b`, `a -> c`, `b -> d`, `c -> d`；当 系统推导 stage；那么 `stage(a)=0`
    假如 workflow DAG 满足 `a -> b`, `a -> c`, `b -> d`, `c -> d`
    当 系统推导 stage
    那么 `stage(a)=0`
  @req:r548 @human
  场景: 观测方可读取每个节点的-stage-归因
    - 必须成立：当 调用方启用 workflow viz 或捕获 workflow node start/end/cancelled 事件；那么 事件/快照中 MUST 可读取每个节点的 `stage`
    当 调用方启用 workflow viz 或捕获 workflow node start/end/cancelled 事件
    那么 事件/快照中 MUST 可读取每个节点的 `stage`
