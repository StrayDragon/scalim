# 可视化工具(Scalim Viz)集成(实验性)

??? note "适用读者"
    - 需要接入/使用可视化工具(Scalim Viz)的开发者与平台同学
    - 需要输出并回放执行事件的使用方

本节描述如何生成 VizGraphSnapshot 与 VizEventStream,并将其提供给可视化前端(Scalim Viz)进行回放与观察.

## 1. 前端目录结构

以下示例以这个目录组织前端:

```
frontend/scalim-viz/
```

依赖管理使用 `pnpm`,前端技术栈以 Svelte + XYFlow 为例.

开发启动:

```bash
cd frontend/scalim-viz
pnpm install
pnpm dev
```

## 2. 运行模式(两种)

1. 离线回放(低侵入)
   - Scalim 正常执行,产出 `viz_snapshot.json` + `viz_events.jsonl`
   - UI 通过目录导入(scalim-viz)一次性加载
2. 实时监控(读文件,轻量)
   - Scalim 正常执行,持续追加 JSONL 文件
   - UI 通过本地目录选择器读取并轮询更新(需要浏览器支持 File System Access)

默认本地输出目录:
- Linux: `~/.config/scalim-viz/`
- macOS: `~/Library/Application Support/scalim-viz/`
- Windows: `%APPDATA%\\scalim-viz\\`

输出目录隔离规则:
- 若配置 `output_dir=/path/to/run-root`,系统会自动追加 `scalim-viz` 并为每个 run 生成独立子目录:
  - `/path/to/run-root/scalim-viz/<run_id>/viz_snapshot.json`
  - `/path/to/run-root/scalim-viz/<run_id>/viz_events.jsonl`
  - (可选) `/path/to/run-root/scalim-viz/<run_id>/viz_trace.jsonl` (`trace_enabled=true`)
- 若配置 `output_dir=/path/to/scalim-viz`,则直接使用该目录:
  - `/path/to/scalim-viz/<run_id>/viz_snapshot.json`
  - `/path/to/scalim-viz/<run_id>/viz_events.jsonl`
  - (可选) `/path/to/scalim-viz/<run_id>/viz_trace.jsonl` (`trace_enabled=true`)
- 若显式配置 `output_path` / `snapshot_path` / `trace_path`,则直接写入指定文件(不创建 run 子目录).
  - 默认会覆盖 JSONL 文件以保证单 run 输出;如需跨 run 追加,请显式设置 `append=true`

## 3. 生成 VizGraphSnapshot

```python
from scalim.planning import PlanBuilder
from scalim.spec.ir import DemandIr

# demand_ir 由 DSL 转换或手动构建得到
plan = PlanBuilder(demand_ir).build()
snapshot = plan.to_viz_graph_snapshot()
```

## 4. 运行时事件流(VizEventStream)

推荐使用 `VizObserver` 输出 JSONL:

```python
from scalim.execution import ScalimEngine
from scalim.ob import Observability
from scalim.ob.presets.viz import VizObserverConfig, VizObserver

config = VizObserverConfig(
    run_id=None,               # (可选) 稳定 run_id(用于输出目录名与事件 run_id);workflow bundle 会自动设置
    output_dir="/path/to/run-root",
    trace_enabled=False,        # true => 额外输出 viz_trace.jsonl
    payload_policy="summary",   # 或 sample/full/none
    append=False,               # 仅当显式 output_path/snapshot_path 时需要;默认覆盖避免跨 run 混写
    run_name="wf:run-003",      # (可选) 更可读的稳定 run 标识,优先于 run_id 展示
    env="prod",                 # (可选) 环境标识,用于 UI 展示
)

# 若已有 ExecutionPlan:
observer = VizObserver.from_plan(plan, config)

observability = Observability(observers=[observer])
observer_manager = observability.build_manager()

engine = ScalimEngine(demand=demand_ir, plan=plan, observer_manager=observer_manager)
engine.run()
```

### YAML DSL: runtime overrides(推荐)

YAML 主线不再承载 `observability.*`(legacy key 会 warning + ignore).如需为 demand/workflow 输出 viz,请在运行入口侧显式启用:

```python
from scalim.dsl.by_yaml import RunOptions, RunOverrides, run
from scalim.ob.presets.viz import VizObserverConfig

run(
    "path/to/demand.yaml",
    options=RunOptions(
        allowed_modules=frozenset(["myapp.loaders"]),
        overrides=RunOverrides(
            viz_config=VizObserverConfig(
                output_dir="/path/to/run-root",
                trace_enabled=False,
                payload_policy="summary",
                run_name="wf:run-003",
                env="prod",
            ),
        ),
    ),
)
```

### 事件体量建议

- `viz_events.jsonl` 始终输出编排级/低频事件,适合默认回放与理解执行流程
- `trace_enabled=true` 时会额外输出 `viz_trace.jsonl` 的高频 trace(字段/行级/lookup 等),建议在 UI 中按需加载并配合过滤/步进使用

当 `VizObserverConfig` 提供 `output_dir`/`output_path`/`snapshot_path`/`use_default_output_dir=True` 等有效输出路径时,viz 会被启用并落盘对应产物.

### workflow 多 runs 建议

- workflow 会产生多次独立运行,每次运行默认落到独立的 `<run_id>` 子目录.
- 为了在 UI 中更可读、更稳定地对拍 runs,建议显式设置:
  - `VizObserverConfig.run_name`: 语义化且稳定的 run 标识(例如 workflow run id)
  - `VizObserverConfig.env`: 环境标识(如 `dev`/`staging`/`prod`)
- UI 展示优先级: `run_name` > `run_id`(fallback).

### workflow replay bundle (MVP)

当执行 workflow YAML(例如 `run_workflow(...)`)时,可以选择导出一个“单目录可携带”的 workflow replay bundle:

- bundle 目录内包含一个 workflow scope run:`scalim-viz/workflow/`
- bundle 目录内包含每个 workflow demand 节点的 child replay run:`scalim-viz/<demand_run_id>/`

启用方式(建议只配置 `output_dir`,不要显式指定 `output_path`/`snapshot_path`/`trace_path`,因为 bundle 需要创建多个 run 子目录):

```python
from scalim.dsl.by_yaml import RunOverrides, run_workflow
from scalim.ob.presets.viz import VizObserverConfig

run_workflow(
    "path/to/workflow.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    overrides=RunOverrides(
        viz_config=VizObserverConfig(
            output_dir="/path/to/run-root",
            trace_enabled=False,
            payload_policy="summary",
        ),
    ),
)
```

输出目录结构:

```text
/path/to/run-root/
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

workflow snapshot linking 规则:

- workflow demand node 的 `node.data.kind` MUST 为 `"workflow_demand"`
- 若可 drill-down,workflow demand node 的 `node.data.demand_run_id` MUST 指向同 bundle 内的子目录名(`<demand_run_id>`)
- 若 child replay 缺失或不完整(至少缺 `viz_snapshot.json`/`viz_events.jsonl`),则 MUST 省略 `demand_run_id`(避免导出 broken link)

workflow scope 的 node id / event node_ref 命名空间:

- workflow node: `workflow_node:{workflow_node_id}`
- workflow resource: `workflow_resource:{resource_type}:{resource_id}`

前端加载到 bundle 时会默认进入 workflow scope(拓扑优先),并支持从 workflow demand 节点 drill-down 到 child demand replay,再返回 workflow scope 并恢复上下文.

### outputs(多输出组合)回放口径

当启用 outputs/多输出组合(output composition)时:
- VizGraphSnapshot 依赖图会包含 `output_target:<target_id>` 节点,并通过 `composed_from` 边连接其输入字段.
- 事件流会输出 `output_target_finished` 事件,用于展示每个输出目标的写出统计与失败状态(行数/耗时/错误/禁用/路径/sheet/错误信息).

## 5. 从 YAML 构建 VizObserver(便捷方式)

```python
from scalim.dsl.by_yaml import RunOptions, RunOverrides, run
from scalim.ob.presets.viz import VizObserverConfig

_ = run(
    "path/to/report.yaml",
    options=RunOptions(
        allowed_modules=frozenset(["myapp.loaders"]),
        overrides=RunOverrides(viz_config=VizObserverConfig(output_dir="/path/to/scalim-viz")),
    ),
)
```

## 6. UI 端接入(本地目录)

可视化前端(Scalim Viz)默认通过本地目录选择器读取 `scalim-viz/` 输出目录,无需 URL 配置或鉴权.

### 示例数据(本地生成,不提交)

示例数据默认生成到(已被 `.gitignore` 忽略):

- `.tmp/artifacts/scalim-viz/examples/demo_big_data_report/events-only/`
- `.tmp/artifacts/scalim-viz/examples/demo_big_data_report/events+trace/`

在 UI 端使用“选择目录(回放)”即可加载.

如需从 YAML 示例重新生成一份输出,可执行:

```bash
just gen-viz-data
```

该命令会生成 demo 的 events-only 输出;如需 trace,可使用 `--mode events+trace`.

UI 也支持直接选择包含上述两个文件的目录进行回放(浏览器支持 `webkitdirectory` 时可用).
若 `scalim-viz/` 目录下存在多个 run 子目录,UI 会列出可选运行进行切换.
