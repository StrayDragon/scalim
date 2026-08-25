# language: zh-CN
# capability: workflow-replay-bundle
# purpose: 定义 workflow 级 replay bundle 导出契约：包含 workflow scope 快照/事件流与 demand child replay 目录，支持 drill-down 引用，保持 child replay 现有协议不变。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: workflow-replay-bundle

  @req:r93 @human
  场景: workflow execution MUST be exportable as a single linked replay bundle
    - 系统 MUST 提供 workflow 级 replay bundle 导出能力，使用户能够通过一次 workflow 级导出得到一个可携带、可直接打开的目录，而不需要手工收集多个 child run replay 目录。 bundle MUST 作为一个单目录存在，并至少包含： - `scalim-viz/workflow/` 下的 workflow scope run - `scalim-viz/<demand_run_id>/` 下的 demand runs（由 workflow 节点引用）

  @req:r335 @human
  场景: bundle MUST include a workflow scope run at `scalim-viz/workflow/`
    - bundle MUST 包含一个 workflow scope run，其 run id MUST 为 `workflow`（即目录 `scalim-viz/workflow/`）。 workflow scope run MUST 至少包含： - `viz_snapshot.json`（workflow 拓扑快照） - `viz_events.jsonl`（workflow 事件流） 并且 MAY 额外包含： - `viz_trace.jsonl`（可选） - `viz_schedule_plan.json`（可选）

  @req:r457 @human
  场景: workflow snapshot MUST provide a workflow-first graph entry
    - `scalim-viz/workflow/viz_snapshot.json` MUST 提供 workflow 级图结构，用于作为 workflow-first 入口视图。 workflow snapshot MUST： - 与现有 snapshot 一样提供 XYFlow 兼容的 `nodes` / `edges` / `meta` - 使用稳定的 node id： - workflow demand node: `workflow_node:{workflow_node_id}` - workflow resource node: `workflow_resource:{resource_type}:{resource_id}` - 对 demand 节点提供可 drill-down 的 child replay 引用信息，并通过 `node.data.demand_run_id` 表达

  @req:r543 @human
  场景: workflow snapshot MUST provide stable drill-down mapping via `demand_run_id`
    - 对每个可 drill-down 的 workflow demand node，workflow snapshot MUST 在 `node.data` 中携带： - `kind="workflow_demand"` - `field_key="<workflow_node_id>"` - `demand_run_id="<demand_run_id>"` 其中： - `demand_run_id` MUST 对应同 bundle 内的 demand replay run id（即目录 `scalim-viz/<demand_run_id>/`） - `demand_run_id` MUST NOT 为绝对路径 workflow snapshot MAY 提供 stages 信息用于 staged layout： - `stages[].field_keys` SHOULD 使用 `<workflow_node_id>` 值（与 `field_key` 对齐），用于前端 stage band/layout

  @req:r614 @human
  场景: workflow events MUST be joinable to workflow snapshot nodes
    - `scalim-viz/workflow/viz_events.jsonl` MUST 承载 workflow 级事件流，并与 workflow snapshot 共享稳定的 node_ref 命名空间。 top-level workflow events MUST 至少覆盖： - `workflow_started` / `workflow_finished` - `workflow_node_started` / `workflow_node_completed` - `workflow_node_cancelled` - `workflow_cache_*` - `workflow_resource_*` 这些事件的 `node_ref.id` MUST 能映射回 `scalim-viz/workflow/viz_snapshot.json` 中的某个节点。

  @req:r663 @human
  场景: bundle MUST preserve existing child replay artifact contracts
    - workflow replay bundle MUST 复用既有单 run replay 产物契约，而不是为 child runs 定义另一套文件格式。 对 child replay 目录： - `viz_snapshot.json` / `viz_events.jsonl` MUST 保持现有口径 - `viz_trace.jsonl` / `viz_schedule_plan.json` MAY 按现有规则缺省 - workflow bundle MAY 在顶层新增文件，但 MUST NOT 破坏 child replay 的既有命名与结构

  @req:r705 @human
  场景: workflow nodes MUST NOT contain broken drill-down references
    - 当 workflow snapshot 的某个节点包含 `demand_run_id` 时，系统 MUST 确保该 run 在 bundle 内存在，并且至少包含： - `viz_snapshot.json` - `viz_events.jsonl` 否则系统 MUST 省略该节点的 `demand_run_id`（使其不可 drill-down），而不是导出一个必然失效的链接。
  @req:r93 @human
  场景: one-workflow-export-creates-a-self-contained-bundle-director
    - 必须成立：当 用户对一次 workflow 执行启用可视化导出；那么 系统 MUST 产出一个 workflow replay bundle 目录
    当 用户对一次 workflow 执行启用可视化导出
    那么 系统 MUST 产出一个 workflow replay bundle 目录
  @req:r335 @human
  场景: workflow-scope-run-is-loadable-as-a-normal-replay-run
    - 必须成立：假如 一个 workflow replay bundle；当 前端以单 run replay 逻辑加载 `scalim-viz/workflow/`；那么 前端 MUST 能加载 snapshot 与 events 并展示 workflow scope 的 graph/timeline
    假如 一个 workflow replay bundle
    当 前端以单 run replay 逻辑加载 `scalim-viz/workflow/`
    那么 前端 MUST 能加载 snapshot 与 events 并展示 workflow scope 的 graph/timeline
  @req:r457 @human
  场景: demand-nodes-can-be-mapped-to-child-replay-directories
    - 必须成立：假如 workflow snapshot 中存在 demand node `workflow_node:orders`；当 前端根据该节点执行 drill-down；那么 系统 MUST 能稳定解析到 `orders` 对应的 child replay 目录
    假如 workflow snapshot 中存在 demand node `workflow_node:orders`
    当 前端根据该节点执行 drill-down
    那么 系统 MUST 能稳定解析到 `orders` 对应的 child replay 目录
  @req:r543 @human
  场景: drill-down-links-are-portable
    - 必须成立：假如 workflow snapshot 中的某个节点包含 `demand_run_id="run_foo"`；当 用户移动整个 bundle 目录到新的位置再打开；那么 前端 MUST 仍能通过 run id 找到 `scalim-viz/run_foo/` 并完成 drill-down
    假如 workflow snapshot 中的某个节点包含 `demand_run_id="run_foo"`
    当 用户移动整个 bundle 目录到新的位置再打开
    那么 前端 MUST 仍能通过 run id 找到 `scalim-viz/run_foo/` 并完成 drill-down
  @req:r614 @human
  场景: resource-lifecycle-events-can-highlight-workflow-graph-nodes
    - 必须成立：假如 workflow bundle 中存在 pathless xlsx 资源节点；当 事件流包含该资源的 `workflow_resource_write`；那么 该事件的 `node_ref.id` MUST 能映射到对应的 workflow resource node
    假如 workflow bundle 中存在 pathless xlsx 资源节点
    当 事件流包含该资源的 `workflow_resource_write`
    那么 该事件的 `node_ref.id` MUST 能映射到对应的 workflow resource node
  @req:r663 @human
  场景: existing-demand-replay-loader-can-open-a-child-replay-unchan
    - 必须成立：假如 workflow bundle 下某个 `scalim-viz/<demand_run_id>/` 目录；当 前端以现有单 run replay 逻辑读取该目录；那么 该目录 MUST 仍可作为一个普通 demand replay 被成功加载
    假如 workflow bundle 下某个 `scalim-viz/<demand_run_id>/` 目录
    当 前端以现有单 run replay 逻辑读取该目录
    那么 该目录 MUST 仍可作为一个普通 demand replay 被成功加载
  @req:r705 @human
  场景: missing-child-replay-does-not-break-opening-the-workflow-run
    - 必须成立：假如 workflow 中存在某个节点无法产出 child replay；当 用户打开 workflow replay bundle 并查看 workflow scope run；那么 workflow scope run MUST 仍可正常打开
    假如 workflow 中存在某个节点无法产出 child replay
    当 用户打开 workflow replay bundle 并查看 workflow scope run
    那么 workflow scope run MUST 仍可正常打开
