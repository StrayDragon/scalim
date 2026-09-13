# language: zh-CN
# capability: workflow-stage-scheduling
# purpose: 为 workflow DAG 提供可配置的调度 preset，使调用方可以在保持默认 pipeline 行为不变的前提下，选择严格的 stage barrier（阶段屏障）调度，以提升可预期性、资源规划与可解释性。 [rev:c25]
# scope: src/scalim/
功能: workflow-stage-scheduling

  @req:r99 @human
  场景: workflow runtime MUST 支持 scheduler preset（pipeline / stage_barrier）
    - 系统 MUST 通过运行期策略边界（runtime policy boundary）提供 workflow scheduler preset 的选择入口：
      - 调用方 MUST 能通过 `workflow_runtime_options.scheduler` 选择调度 preset（以 typed dataclass 作为策略对象）。
      - 默认调度 preset MUST 为 `pipeline`；`stage_barrier` MUST 为显式 opt-in（并明确其 trade-off）。仅阅读 spec（不打开源码）MUST 能明确知道该默认与 opt-in 关系。
      - 对外公开概念 MUST 统一为 `stage`（不得引入 `wave` 等同义概念作为公共表面）。
    假如 workflow 包含两个 stage 0 节点 `a` 与 `x`（均无 deps），以及一个 stage 1 节点 `b`（`b depends_on [a]`）
    当 调用方以 `workflow_runtime_options.scheduler=pipeline` 运行该 workflow
    那么 系统 MUST 允许在 `x` 尚未终态时启动 `b`（只要 `a` 已终态且 worker 有空闲）
  @req:r341 @human
  场景: stage_barrier scheduler MUST 强制严格阶段屏障
    - 当调用方选择 `stage_barrier` preset 时，系统 MUST 以“阶段”为屏障推进调度： - 定义 stage（demand 节点）：`stage(node) = max(stage(dep)) + 1`（无 deps 则为 0） - 对内部 write nodes：系统对外暴露的 `stage` MUST 折叠到其输入 demand 的 stage（避免把内部写入步骤误解为新的业务阶段） - 系统 MUST NOT 启动 stage `k+1` 的任一节点，直到 stage `k` 的所有节点均到达终态（成功/失败/取消）
    假如 workflow 包含两个 stage 0 节点 `a` 与 `x`（均无 deps），以及一个 stage 1 节点 `b`（`b depends_on [a]`）
    当 调用方以 `workflow_runtime_options.scheduler=stage_barrier` 运行该 workflow
    那么 系统 MUST NOT 在 `x` 到达终态前启动 `b`
  @req:r463 @human
  场景: stage 推导 MUST 确定且可解释
    - 系统 MUST 基于 workflow DAG 拓扑推导 stage 归因，并保持确定性： - 对同一份 workflow IR（相同的 nodes/deps），`stage_by_node_id` 的结果 MUST 稳定且不依赖并发完成时序 - 当 DAG 编译阶段发现 cycle 时，系统 MUST 快速失败（fail-fast）（stage 推导仅作为可观测性/布局/调度的派生信息）
    假如 workflow DAG 满足 `a -> b`, `a -> c`, `b -> d`, `c -> d`
    当 系统推导 stage
    那么 `stage(a)=0`
  @req:r548 @human
  场景: schedule_mode 与 stage MUST 可观测
    - 系统 MUST 对外暴露最小可观测性信息，用于解释执行顺序：
      - 对每个 workflow node，系统 MUST 能暴露其 `stage` 归因
      - 系统 MUST 能暴露本次 workflow 的 `schedule_mode`（`pipeline` 或 `stage_barrier`）
      - 新增诊断字段时 MUST 优先扩展 `viz snapshot`；仅当字段被证实需要“事件流强消费”时，才 SHOULD 扩展 workflow node 事件 payload，并 MUST 明确字段稳定性与版本策略。
    当 调用方启用 workflow viz 或捕获 workflow node start/end/cancelled 事件
    那么 事件/快照中 MUST 可读取每个节点的 `stage`
  @req:r100 @human
  场景: workflow stage scheduling residual risks MUST be tracked as a stable risk register
    - 系统 MUST 维护一份稳定可发现的 risk register，避免风险仅存在于临时讨论记录、commit message 或归档后难以发现的单次 change proposal。条目结构与登记内容：

      | ID | Risk | Signals | Mitigations | Touchpoints |
      | --- | --- | --- | --- | --- |
      | R1 | `stage_barrier` 可能吞吐下降或 wall time 放大 | 节点终态与启动时序、wall time 对比 | 默认 `pipeline`；`stage_barrier` 显式 opt-in 并写明 trade-off | 本 spec r99/r341 |
      | R2 | 内部 write nodes 的 `stage` 折叠可能被误解为“少一层” | 诊断视图中 stage 数量 | write nodes 的 `stage` 折叠到输入 demand 的 stage | 本 spec r341 |
      | R3 | 可观测字段扩展的兼容性风险（`viz snapshot` vs 事件 payload） | snapshot/事件字段差异 | 优先扩展 snapshot；事件 payload 需声明稳定性与版本策略 | 本 spec r548 |
      | R4 | 术语漂移导致概念分叉（`wave` vs `stage`） | 文档/事件中的同义概念 | 对外统一 `stage` | 本 spec r99 |
      | R5 | 性能“印象”被误当作严谨 benchmark | 材料开头是否声明 | 按 r549 标注非 benchmark 与局限性 | 本 spec r549 |
    - 维护者修改 scheduler preset、`stage` 归因或相关可观测字段时，MUST 对照该 register 逐条确认影响与缓解。
    假如 维护者计划修改 `workflow` 的 scheduler preset、`stage` 归因或相关可观测字段
    当 维护者准备实现或验收该变更
    那么 维护者 MUST 对照 risk register 逐条确认影响与缓解
  @req:r549 @human
  场景: performance impression artifacts MUST be labeled as non-benchmark
    - 当仓库提供对比 `pipeline` 与 `stage_barrier` 的性能材料（notebook/demo/report）时，系统 MUST 在材料开头明确区分 **Impression / Trend**（直观对比、排障复现）与 **Benchmark**（固定数据集、隔离环境、可重复套件），并写清样本规模、环境与局限性，避免结论被误读为严谨 benchmark。
    当 维护者打开性能对比材料
    那么 MUST 能在开头看到“非 benchmark”的声明与局限性说明
