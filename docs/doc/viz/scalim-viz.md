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
    output_dir="/path/to/run-root",
    trace_enabled=False,        # true => 额外输出 viz_trace.jsonl
    payload_policy="summary",   # 或 sample/full/none
    append=False,               # 仅当显式 output_path/snapshot_path 时需要;默认覆盖避免跨 run 混写
)

# 若已有 ExecutionPlan:
observer = VizObserver.from_plan(plan, config)

observability = Observability(observers=[observer])
observer_manager = observability.build_manager()

engine = ScalimEngine(demand=demand_ir, plan=plan, observer_manager=observer_manager)
engine.run()
```

### YAML DSL 内配置(推荐)

```yaml
observability:
  viz:
    enabled: true
    output_dir: /path/to/run-root
    trace_enabled: false
    append: false
    payload_policy: summary
    sample_size: 5
```

### 事件体量建议

- `viz_events.jsonl` 始终输出编排级/低频事件,适合默认回放与理解执行流程
- `trace_enabled=true` 时会额外输出 `viz_trace.jsonl` 的高频 trace(字段/行级/lookup 等),建议在 UI 中按需加载并配合过滤/步进使用

如果仅配置 `output_dir` / `output_path` / `snapshot_path` / `use_default_output_dir`,可省略 `enabled`,系统会自动开启.

## 5. 从 YAML 构建 VizObserver(便捷方式)

```python
from scalim.dsl.by_yaml.runtime.introspection import build_viz_observer
from scalim.execution import ScalimEngine
from scalim.ob import Observability

observer = build_viz_observer(
    yaml_path="path/to/report.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    config=VizObserverConfig(output_dir="/path/to/scalim-viz"),
)

observability = Observability(observers=[observer])
observer_manager = observability.build_manager()
engine = ScalimEngine(demand=demand_ir, plan=plan, observer_manager=observer_manager)
engine.run()
```

## 6. UI 端接入(本地目录)

可视化前端(Scalim Viz)默认通过本地目录选择器读取 `scalim-viz/` 输出目录,无需 URL 配置或鉴权.

### 示例数据(内置 artifacts)

当前示例数据已放入:

- `artifacts/scalim-viz/examples/demo_big_data_report/events-only/`
- `artifacts/scalim-viz/examples/demo_big_data_report/events+trace/`

在 UI 端使用“选择目录(回放)”即可加载,不再通过 public 目录或“加载样例”按钮.

如需从 YAML 示例重新生成一份输出,可执行:

```bash
just gen-viz-data
```

该命令会生成 demo 的 events-only 输出;如需 trace,可使用 `--mode events+trace`.

UI 也支持直接选择包含上述两个文件的目录进行回放(浏览器支持 `webkitdirectory` 时可用).
若 `scalim-viz/` 目录下存在多个 run 子目录,UI 会列出可选运行进行切换.
