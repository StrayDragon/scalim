## Context

当前 `scalim-viz` 已经能很好地处理单次 demand 回放与 adaptive 计划视角，但 workflow 使用方仍处在“多目录、多入口、弱联动”的状态：

- 顶层没有 workflow-first 视图，用户无法直接把编排层当成业务模块图来查看
- workflow 运行后默认只得到多个 child run 目录，分享或归档时需要额外说明“先开哪个，再点哪个”
- workflow runtime 已经具备足够的结构信号：`workflow_node_id` 稳定、workflow 事件族稳定、共享资源和 cache 生命周期也能被 join；缺的是对这些信号的 replay bundle 组织与前端交互解释

用户明确希望：

- 初始画面是 workflow 节点视图，而不是 demand 字段图
- 点击某个 demand 节点后，进入现有 demand 视角分析
- 导出结果是一个目录，内部天然联动，便于业务方携带/共享

约束：

- 核心运行时仍需兼容 Python 3.6
- 不手改任何 `.gen.*` 文件与 injected blocks
- `frontend/scalim-viz/` 现有单 run 回放能力必须保留

## Goals / Non-Goals

**Goals:**

- 定义一个 workflow replay bundle 契约，使一次 workflow 导出产出一个可携带的单目录
- 让 `frontend/scalim-viz/` 在检测到该 bundle 时，以 workflow 视图作为默认入口
- 支持从 workflow demand 节点 drill down 到 child demand replay，并保持返回上下文
- 复用现有 demand replay 文件契约，避免为 child run 重新设计一套 artifacts
- 将 UI 交互收敛到直觉型层级导航：workflow -> demand replay，而不是“多标签页拼凑”

**Non-Goals:**

- 不在 MVP 中把 workflow DAG 与 demand 字段依赖图画在同一张画布上
- 不在 MVP 中暴露 workflow 内部 write nodes 作为主视图中的一等交互节点
- 不要求支持对任意历史散落目录做 post-hoc 自动 bundling
- 不修改 workflow YAML authoring surface

## Decisions

### 1) 使用单目录 workflow replay bundle，而不是“多个平级 run 目录 + 外部说明”

MVP 采用单目录 bundle,并继续使用既有 `scalim-viz/<run_id>/` 的 run 目录结构,把 workflow 作为一个特殊 run 输出：

```text
<bundle_root>/
  scalim-viz/
    workflow/
      viz_snapshot.json
      viz_events.jsonl
      viz_trace.jsonl           # optional
      viz_schedule_plan.json    # optional
    <demand_run_id>/
      viz_snapshot.json
      viz_events.jsonl
      viz_trace.jsonl           # optional
      viz_schedule_plan.json    # optional
```

决策理由：

- 最符合用户“导出一个目录即可联动”的需求
- workflow 与 demand 的 scope 分层清晰(两个 run),不混到同一张图里
- workflow 与 demand run 仍沿用现有文件名与前端解析逻辑,降低实现风险
- bundle 整体移动/分享天然可用(无绝对路径依赖)

替代方案：

- 继续只输出多个独立 run 目录：最省实现，但完全不满足 workflow-first 入口
- 额外引入 `viz_bundle_manifest.json` 等新文件：可表达更强,但会把 bundle 契约复杂度前置到 MVP
- 将 workflow 与 child replay 全塞在一个 JSON 中：可移植,但体积大、增量加载差、复用现有 demand 回放逻辑困难

### 2) 不引入强制 manifest: workflow->demand linking 通过 `demand_run_id` 直接在 snapshot 中表达

workflow 入口 run 的 `viz_snapshot.json` 负责 workflow 图结构,并直接表达 drill-down 的映射关系。

对每个可 drill-down 的 workflow demand 节点,workflow snapshot MUST 在 `node.data` 中携带：

- `kind="workflow_demand"`
- `demand_run_id="<demand_run_id>"`

决策理由：

- snapshot 保持“图结构”单一职责
- `demand_run_id` 是最小闭环:前端只需要在同一 bundle 内按 run id 打开对应 replay
- bundle 内部联动不依赖绝对路径,天然可移植
- UI 不需要理解更多 bundle 文件类型即可工作(降低 MVP 成本)

替代方案：

- 额外引入 manifest(`viz_bundle_manifest.json`):能更好表达 availability/缺失原因,但会扩大后端 writer 与前端 loader 的改动面
- 只扫描目录结构：无显式契约,便携但脆弱,也不利于后续做远程加载/权限边界控制

### 3) workflow 初始视图以 demand 节点为主，资源关系作为辅助，不把 write nodes 做成主视图主角

workflow graph 节点类型在 MVP 中收敛为：

- `workflow_node:{workflow_node_id}`：主要是 demand 节点
- `workflow_resource:{resource_type}:{resource_id}`：共享资源节点（按需出现）

边类型收敛为：

- `depends_on`
- `writes_to`
- `reads_from_resource`（当存在显式资源读取语义时）

这里不把 write nodes 作为初始画面主节点，原因是用户明确想先看“业务逻辑模块”。write 行为仍保留在 inspector / workflow events 中解释。

替代方案：

- 暴露所有 IR 节点（含 write nodes）：语义最全，但主画布会迅速偏实现细节，不利于业务方理解
- 只展示 demand 节点，不展示资源：过于简化，难以解释 workflow 共享输出的真实结构

### 4) top-level workflow events 复用 `vizevent/v1`，但使用新的 workflow node_ref 命名空间

workflow scope 的 `scalim-viz/workflow/viz_events.jsonl` 继续复用 `vizevent/v1`,避免多一套事件 envelope。新增 node_ref 约定：

- workflow node: `workflow_node:{workflow_node_id}`
- workflow resource: `workflow_resource:{resource_type}:{resource_id}`

workflow 事件流主要承载：

- `workflow_started` / `workflow_finished`
- `workflow_node_started` / `workflow_node_completed`
- `workflow_node_cancelled`
- `workflow_cache_*`
- `workflow_resource_*`

这样 workflow snapshot 与 workflow events 可天然联动；child demand events 仍留在各自 run 目录，不混入顶层时序。

替代方案：

- 新建完全不同的 workflow event schema：区分更强，但会把前端/后端两边同时复杂化
- 将 workflow events 和 child demand events 混写到一个 JSONL：会破坏两层视图边界

### 5) 前端采用 workflow-first 层级导航，而不是多视图平铺切换

当目录加载到多个 run,且存在 `workflow` run 时：

- 默认进入 workflow graph
- 点击 demand 节点后进入对应 demand replay
- 通过 back action 返回 workflow graph
- 返回时保留：
  - workflow 选中节点
  - workflow 画布视口
  - workflow 的 timeline/playback 上下文与过滤/聚焦状态(见下文)

交互原则参考本次 UI/UX 调研，收敛为：

- 层级可见：breadcrumb 必须清晰
- 键盘可达：tab 顺序与视觉顺序一致，提供 skip link
- 动画克制：150-300ms，支持 `prefers-reduced-motion`
- 关键动作不依赖 hover
- 焦点态清晰，可一眼看出当前 scope 在 workflow 还是 demand

决策理由：

- workflow -> demand 是天然父子关系，层级导航比“切模式”更符合心智
- 保留上下文能降低来回对照的认知负担

### 6) 状态保持方案: MVP 用单层 return snapshot,后续可升级

用户核心诉求是"来回定位和回溯"。MVP 选择单层 return snapshot:

- 从 workflow 进入 demand 时,保存 workflow 状态快照
- 在 demand scope 提供"返回 workflow"
- 返回后恢复 workflow 状态(包括 viewport)

这是最小闭环,实现成本低,且不会引入复杂的导航栈边界问题。

替代/后续演进:

- 导航栈(stack):允许多层 drill-down(例如 workflow->demand->row),需要统一 history 语义与回收策略
- per-run UI state map:对每个 run 记忆最后一次 UI 状态,支持在多个 demand 之间快速切换,但需要定义"何时重置"的原则

### 7) 简单导出路径优先通过 workflow 级 writer 协调完成，而不是要求用户自己收集 child replays

本提案要求系统提供一个 workflow 级导出路径，调用一次即可得到完整 bundle。实现形式可以是：

- workflow runtime 在启用 viz 导出时自动写 bundle
- 或 workflow 级 helper/writer 在一次执行结果上完成 bundle 写出

但无论底层入口怎么设计，用户不应该手工拼接目录。

## Risks / Trade-offs

- [bundle 复杂度上升] → 通过复用既有 run 目录结构与文件名,把新增复杂度集中在 workflow run 的 snapshot/events 产出与前端导航
- [workflow graph 过于“工程化”] → MVP 以 demand 节点为主，不暴露 write nodes；资源仅作为辅助关系
- [top-level / child events 双层并存导致前端状态更复杂] → 明确 workflow 与 demand 是两套 state scope，禁止混在同一时间轴里
- [child replay 缺失或不完整] → 前端以禁用 drill-down + 说明文案降级,而不是报错中断(availability 机制后续可扩展)
- [文档与示例漂移] → 手工维护 `docs/doc/viz/scalim-viz.md` 与 `frontend/scalim-viz/README.md`，其余生成页通过 `just gen-docs` 刷新

## Migration Plan

- 旧的单 run replay 保持不变，仍可直接通过目录导入
- 新增 workflow run 作为增量入口；当前 `frontend/scalim-viz/` 在检测不到 `workflow` run 时,继续走旧逻辑
- 文档上先补 workflow-first 入口与目录结构说明，再根据实现补 demo bundle
- 验证顺序：
  1. `openspec validate --all --strict --no-interactive`
  2. `just openspec-check`
  3. 相关前后端测试
  4. `just gen-docs`
  5. `just qa`

## Resolved Interaction Decisions

### 1) 共享资源状态采用“主图轻徽标 + inspector / event stream 细节”组合，而不是只藏在次级面板

通过本次 workflow UI demo 对比，纯 inspector 方案会让用户在 workflow 层无法快速判断“信息从哪来”。因此设计收敛为:

- workflow graph 可以直接出现资源节点
- 资源节点与 demand 节点上允许出现轻量状态提示
- 详细生命周期、原因与事件证据仍进入 inspector / event stream 查看

这满足用户“怎么能方便使用者获取信息怎么来”的目标，同时避免资源状态完全喧宾夺主。

### 2) child demand 默认不是固定 timeline 落点，而是“静态底图优先 + replay 作为覆盖层”

workflow-first 交互 demo 验证后，默认落点收敛为:

- workflow 是顶层主视图
- 点击 workflow demand 节点后，进入 child demand 工作台
- child demand 先进入最适合该节点的静态底图:
  - `graph` 适合结构型节点
  - `adaptive` 适合并发/计划型节点
- `replay` 不再被视为孤立第三视图，而是覆盖在当前静态底图上的时间维/证据层

也就是说，默认落点按 artifact 与节点语义选择，而不是固定 timeline。

### 3) MVP 推荐交互形态定为“workflow 主视图 + 完整 drill-down 工作台”

在三种 demo 中:

- 右侧工作台方案更适合侦查，但 demand 深分析空间不足
- 左右分栏方案联动强，但对窄屏不友好
- workflow 主视图 + 完整 drill-down 工作台最符合用户的层级心智

因此提案推荐:

- workflow 作为 bundle 默认入口
- demand 通过 route-level / workspace-level drill-down 打开
- 浏览器返回与 breadcrumb 负责恢复 workflow 上下文
