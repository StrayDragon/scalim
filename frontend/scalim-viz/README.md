# Scalim Viz (Svelte + XYFlow)

极简可视化前端: 单画布 + 勘察面板 + 数据源抽屉.

## 视图分工(Seq vs Adaptive)

- **Seq**:时间线(时序图)仍是主入口,按事件推进查看数据流转.
- **Adaptive**:推荐使用 **执行计划**(计划视角)查看 fanout/fanin/屏障等结构;事件流作为“证据视角”,不把 `timestamp` 当作真实并发重叠还原.
  - 若目录缺失 `viz_schedule_plan.json`,执行计划会提示“无计划数据”,仅保留证据视角能力.

## 开发

```bash
pnpm install
pnpm dev
```

### DevTools 快速打开(开发模式)

开发模式支持通过 URL 参数自动加载回放目录(无需目录选择;路径相对仓库根目录,仅允许读取 `artifacts/scalim-viz/` 下的文件):

- Seq/Adaptive:`/?replay=artifacts/scalim-viz/examples/demo_big_data_report/events-only/scalim-viz/run_demo_big_data_events`
  - 该样例目录内已包含 `viz_schedule_plan.json`,因此可直接在 UI 中切换到 Adaptive(计划视角)。

## Workflow Bundle (MVP)

当导入的目录包含 `scalim-viz/workflow/` 这个 run 时,UI 会默认进入 workflow scope(拓扑优先),并把 workflow 的时间线事件展示为 workflow 自己的执行时序。

workflow scope 的 demand 节点若携带:

- `node.data.kind="workflow_demand"`
- `node.data.demand_run_id="<run_id>"`

则 inspector 会提供“进入 demand 视图”,打开同目录下 `scalim-viz/<run_id>/` 对应的 demand replay;并提供“返回 workflow”,恢复 workflow 上下文(选中节点、timeline/playback、stage filter、focus、viewport)。

目录结构示意:

```text
<bundle_root>/
  scalim-viz/
    workflow/
      viz_snapshot.json
      viz_events.jsonl
    <demand_run_id>/
      viz_snapshot.json
      viz_events.jsonl
      viz_trace.jsonl           # optional
      viz_schedule_plan.json    # optional
```

说明:
- 当前 `/?replay=...` URL 仅能自动加载单个 run 目录;workflow bundle(多 run)请用“选择目录(回放)”导入整个目录。
- 仓库内置 workflow bundle 样例目录:
  - `artifacts/scalim-viz/examples/demo_big_data_report/workflow-bundle/`(在 UI 中选择该目录或其下的 `scalim-viz/` 目录均可)

## 目录结构(核心)
- `src/domain/`: 纯逻辑/类型/选择器(无 IO/DOM).
- `src/services/`: 文件读取等副作用封装.
- `src/ui/panels/`: 画布/时间线/检查器/数据源面板等 UI 组件.
- `src/components/`: 业务节点组件(Source/Loader/Field/Derived/Stage).
- `src/libs/components/`: UI primitives(shadcn/bits-ui).
- `src/app/`: 顶层壳(AppShell).

## 交互模式
- 离线回放
  - 通过目录导入:
    - `viz_snapshot.json`(依赖图)
    - `viz_events.jsonl`(事件流)
    - `viz_trace.jsonl`(可选,高频 trace)
    - `viz_schedule_plan.json`(可选,Adaptive 计划视角)
  - 适合低成本调试/回放

## 示例
- `viz_snapshot.json` 可由 `ExecutionPlan.to_viz_graph_snapshot()` 生成并保存
- `viz_events.jsonl` 为编排级事件流(默认输出)
- `viz_trace.jsonl` 为高频 trace(需 `observability.viz.trace_enabled=true`)
  - UI 默认仅加载 `viz_events.jsonl`;在“加载”面板切换到 `events+trace` 后才会按需加载 trace
- `viz_schedule_plan.json` 为计划视角产物(fanout/fanin/屏障),可由 `ExecutionPlan.to_viz_schedule_plan()` 生成并保存
- 默认输出目录示例:`~/.config/scalim-viz/<run_id>/viz_*.json`
- 仓库内置示例位于:
  - `artifacts/scalim-viz/examples/demo_big_data_report/events-only/`
  - `artifacts/scalim-viz/examples/demo_big_data_report/workflow-bundle/`
  使用“选择目录(回放)”选择对应目录即可(示例目录内含 `scalim-viz/<run_id>/viz_*`).

### 生成更多样例(可选)

如需生成更多 profile/场景(例如 trace 或不同 parallel_mode),可使用:

- `just gen-viz-data`(默认 events-only)
- `uv run python scripts/gen-viz-data.py --mode events+trace`

### 生成/补齐 schedule plan

- 生成 demo viz 数据:`just gen-viz-data`(会输出 `viz_schedule_plan.json` 到 demo 目录)
- 对 demo 目录补齐:`just gen-viz-schedule-plan`
- 对任意回放目录补齐:`uv run python scripts/gen-viz-schedule-plan.py --events-jsonl <run>/viz_events.jsonl --output-json <run>/viz_schedule_plan.json`
