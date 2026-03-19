## ADDED Requirements

### Requirement: workflow replay bundle MUST be a first-class UI entry
当前端加载到 workflow replay bundle 时，系统 MUST 将 workflow 视图作为默认入口，而不是直接落到某个 child demand replay。

workflow 入口 MUST 基于 workflow scope run(`scalim-viz/workflow/`)内的 `viz_snapshot.json` 与 `viz_events.jsonl` 渲染 workflow 级图与状态摘要。

#### Scenario: workflow bundle opens at workflow scope by default
- **GIVEN** 用户加载一个包含 `scalim-viz/workflow/` run 的目录
- **WHEN** 前端完成初始化
- **THEN** 初始画面 MUST 为 workflow 视图
- **AND** 用户 MUST 能看到 workflow demand 节点，而不是被直接带入某个 child run

### Requirement: frontend MUST support drill-down from workflow demand nodes to child demand replay
前端 MUST 支持从 workflow demand 节点 drill-down 到对应的 child replay，并提供可预测的返回路径。

drill-down 交互 MUST 满足：

- 点击 demand 节点后，前端 MUST 能通过 `node.data.demand_run_id` 打开对应 demand run
- 返回 workflow 视图时 MUST 保留原先的 workflow 上下文(至少包含: viewMode、playbackIndex、选中节点、stage filter、focus、viewport)
- 当 child replay 缺失时，前端 MUST 给出可读的降级说明

#### Scenario: returning from demand replay preserves workflow context
- **GIVEN** 用户在 workflow 视图中选中了节点 `orders`
- **WHEN** 用户 drill-down 到 `orders` 的 child replay 后再返回 workflow 视图
- **THEN** 前端 MUST 回到先前的 workflow 上下文，而不是重置到默认位置

### Requirement: workflow demand nodes MUST expose an obvious drill-down affordance
workflow scope 画布中的 demand 节点 MUST 能一眼看出其 scope/语义,并提供可发现的 drill-down 动作(例如在 inspector 中出现"进入 demand 视图")。

#### Scenario: users can discover demand drill-down without guesswork
- **GIVEN** 用户打开 workflow scope 画布并选中一个 workflow demand 节点
- **WHEN** 用户查看 inspector
- **THEN** inspector MUST 展示该节点的 workflow 上下文信息
- **AND** inspector MUST 提供进入对应 demand run 的动作入口

### Requirement: workflow-first navigation MUST remain intuitive and accessible
workflow-first 回放 MUST 使用清晰的层级导航，而不是让用户在多个平铺视图中猜测当前 scope。

前端 MUST 至少满足：

- 提供 breadcrumb 或等价层级导航
- 键盘可达，tab 顺序与视觉顺序一致
- 提供清晰的 focus states
- 支持 `prefers-reduced-motion`
- 关键 drill-down / back 操作 MUST NOT 依赖 hover

#### Scenario: keyboard users can move between workflow scope and demand scope
- **WHEN** 用户仅使用键盘操作 workflow bundle 回放
- **THEN** 用户 MUST 能进入 child replay 并返回 workflow 视图
- **AND** 所有关键控件都 MUST 可聚焦且具有可见 focus 状态

### Requirement: workflow bundle loading MUST be additive to existing single-run replay loading
workflow bundle 支持 MUST 为增量扩展，不得破坏现有单 run replay 入口。

#### Scenario: standalone demand replay still works without workflow files
- **GIVEN** 用户加载一个只包含 `viz_snapshot.json` / `viz_events.jsonl` 的旧目录
- **WHEN** 前端完成初始化
- **THEN** 前端 MUST 继续按现有单 run replay 逻辑工作

## MODIFIED Requirements

### Requirement: node_ref 命名规范
系统 SHALL 为 VizEvent 的 `node_ref` 使用稳定且可读的命名规范,确保跨快照与事件流一致。

#### Scenario: node_ref id 规范
- **WHEN** 生成 VizEvent 的 node_ref
- **THEN** id MUST 遵循以下格式:
  - pipeline: `pipeline`
  - batch: `batch:{batch_num}`
  - loader: `loader:{loader_name}`
  - field: `field:{field_key}`
  - source: `source:{source_id}`
  - output_target: `output_target:{target_id}`
  - workflow_node: `workflow_node:{workflow_node_id}`
  - workflow_resource: `workflow_resource:{resource_type}:{resource_id}`
