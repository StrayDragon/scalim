# Run Stats（低漂移自我观测）

??? note "适用读者"
    - 需要用证据判断 loader / compute / relation / 框架优化方向的开发者
    - 需要 workflow 多 demand 汇总、而非「最后一次 pipeline」末态指标的同学
    - 下游用 Agent 装配观测时，可同时加载 `agentdev/skills/scalim-run-stats/`

## Why（为什么需要）

两类证据会误导优化方向：

1. **workflow 假空**：共享 `PerformanceObserver` / `RelationObserver` 会在下一 `PIPELINE_START` reset，末态像「没跑过」。
2. **write 假零**：现代 sink 不走计划层 `WRITE_*`，`stages.write == 0` 会被读成「写出很快」；streaming flush 还可能把时间算进 loader/compute。

`scalim_run_stats/v1` + profiles + write 归因，把「自我观测」和「阶段归因」接到同一 lite 事件平面，给用户负载与框架 A/B 同一份可对拍证据。

## 原则

- **默认静默**：生产可不装配任何 observer（`components=[]`）。
- **bench 低漂移**：只订 lite 事件；墙钟税通常为个位数百分比量级（以本机合成矩阵为准）。
- **debug 显式且警告**：relation / field_compute top-N / viz 等高影响面会 `UserWarning`，并提示改用 bench。
- **workflow 用 `nodes[]`**：共享 observer 会在下一 `PIPELINE_START` reset；完整结论读 `run_stats.nodes`，不要只读 `PerformanceObserver` 末态。
- **write 归因**：现代 sink 路径（column / streaming flush / `sink.close()`）在订阅 `STAGE_SPAN` 时计入 `stages.write`；若写出嵌在 loader/compute 计时窗内会扣回外层，避免双计。

## ROI（怎么用）

| 目标 | 做法 |
|------|------|
| 低漂移日常证据 | `ObservabilityProfile.BENCH` → `accum.build_run_stats()` 的 `nodes[]` / `stages_total` / `loaders` |
| 墙钟对照 | 同输入再跑 `BASELINE`，比 wall；CSV/行内容应对拍不变 |
| 内存趋势 | `BENCH_PLUS` 或 `include_memory=True`（需 psutil；缺失 fail-fast） |
| 短窗深挖 | `DEBUG`（会 warn）；不要当默认生产配置 |
| 落盘 / viz | `write_run_stats_sibling(run_dir, stats)` → 旁路 `run_stats.json`，**勿**塞进 `viz_snapshot.json` |
| 自动旁路 | 同一 observer 集合上同时有 accum + Viz 时，`run_ir` / workflow 收尾 **MAY** 自动写出 sibling |
| 看写出成本 | 订阅 `STAGE_SPAN` 后读 `stages.write` / `stage_metrics.write_duration` |

合成矩阵经验量级（本机、**非 SLA**）：

| scale | bench tax | bench_plus | debug tax | write 归因 |
|-------|-----------|------------|-----------|------------|
| mid 200k | ~**+2%** | ~**+3%** | ~**+41%** | 双节点 `write>0`；CSV equiv OK |
| stress 1M | ~**0% ± 噪声** | （通常跳过） | （通常跳过） | `stages_total.write≈7s`；CSV equiv OK |

可复现 harness + 钉住 evidence：[`llmanspec/.../c50-.../mvp/`](repo:llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/README.md?ref)。本地再跑 JSON 默认落在 `.tmp/obs-demo/runs/`（不入库，后续可给 scalim-viz 观测）。

## 最佳实践（摘要）

1. 日常只开 **bench**；debug 仅短窗，并接受警告与高税。
2. workflow 永远读 **`nodes[]`**，不要读共享 Perf 末态。
3. 对拍用 **CSV 哈希** + 墙钟税；不要用 xlsx 字节相等当业务等价。
4. `stage_sum` 用于相对热点；**墙钟**用于观测税；二者不必相等。
5. 落盘用 sibling `run_stats.json`；Agent 细则见 `agentdev/skills/scalim-run-stats/references/best-practices.md`。

## Profiles

```python
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
# DemandRunRuntimeOptions(components=built["components"], ...)
# after run:
accum = built["handles"]["accum"]
stats = accum.build_run_stats(meta=built["meta"])
write_run_stats_sibling("/path/to/viz-run-dir", stats)  # sibling, not embedded in snapshot
```

| Profile | 用途 |
|---------|------|
| `ObservabilityProfile.BASELINE` | 无组件，墙钟对照 |
| `ObservabilityProfile.BENCH` | 日常自我观测 |
| `ObservabilityProfile.BENCH_PLUS` | + stage memory（需 psutil） |
| `ObservabilityProfile.DEBUG` | 深挖（有警告） |

Memory 采样需要可选依赖 `psutil`；缺失时 **fail-fast**（不静默空 peak）。

## Write stage 口径

- 订阅 `STAGE_SPAN` 时，column / streaming 的真实 sink I/O 计入 `write`。
- `sink.close()` / workbook save 也计入 **write**（非单独 finalize 桶）；该片段可能在最后一次 `BATCH_END` 之后发出，`PerformanceObserver` 会在 `PIPELINE_END` 折叠进 `stage_metrics`。
- 若写出嵌在 loader/compute 计时窗内（如 LOAD_REF 段内列写出），会从外层扣回，避免双计。

## 装配 + 对拍（可直接粘贴）

### Demand（YAML DSL runtime）

```python
import hashlib
import time
from pathlib import Path

from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    run,
)
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

DEMAND = "path/to/demand.yaml"
ALLOWED = frozenset(["myapp.loaders"])  # 按项目 allowlist 改
OUT_CSV = Path("path/to/output.csv")  # 若 demand 写出固定路径


def _run(profile):
    built = build_observability_profile(profile, include_memory=False)
    t0 = time.perf_counter()
    run(
        DEMAND,
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED),
            runtime=DemandRunRuntimeOptions(components=list(built["components"])),
        ),
    )
    wall_s = time.perf_counter() - t0
    stats = None
    accum = built["handles"].get("accum")
    if accum is not None:
        stats = accum.build_run_stats(meta=built["meta"])
        write_run_stats_sibling(".tmp/run-stats-demo", stats)
    digest = hashlib.sha256(OUT_CSV.read_bytes()).hexdigest() if OUT_CSV.is_file() else None
    return wall_s, digest, stats


base_wall, base_hash, _ = _run(ObservabilityProfile.BASELINE)
bench_wall, bench_hash, bench_stats = _run(ObservabilityProfile.BENCH)

assert base_hash == bench_hash  # 业务输出不应因 lite 观测改变
tax = (bench_wall / base_wall - 1.0) if base_wall > 0 else None
# 读证据：bench_stats["nodes"], bench_stats["stages_total"], bench_stats["loaders"]
```

### Workflow（共享 components + nodes[]）

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    WorkflowRunOptions,
    run_workflow,
)
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
demand_opts = DemandRunOptions(
    security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
    runtime=DemandRunRuntimeOptions(components=list(built["components"])),
)
run_workflow("path/to/workflow.yaml", options=WorkflowRunOptions(demand=demand_opts))

accum = built["handles"]["accum"]
stats = accum.build_run_stats(meta=built["meta"])
assert stats["pipeline"]["node_count"] >= 1
# 多 demand：len(stats["nodes"]) 应对齐实际跑完的 pipeline 数
write_run_stats_sibling(".tmp/run-stats-workflow", stats)
```

> 若 workflow 入口另有 `workflow_components` / patch 扩展 components，以当前 runtime API 为准；**结论面仍是 `run_stats.nodes`，不是共享 Perf 末态**。

### Engine（无 YAML）

```python
from scalim.execution.engine import ScalimEngine
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
engine = ScalimEngine(
    demand=demand,
    plan=plan,
    runtime_bindings=runtime_bindings,
    observer_manager=ObserverManager(observers=list(built["components"])),
)
# engine.run(...); then built["handles"]["accum"].build_run_stats(...)
```

## 风险与边界

- **观测税**：debug / relation / field_compute top-N / viz_trace|full / 超大批次 `batches[]` 会抬墙钟；已强制 `UserWarning` 并指向 bench。
- **默认仍静默**：生产可继续不装 observer；启用才有税。
- **读错面**：只看共享 observer 末态会再次「假空」——必须以 `run_stats.nodes` 为全 workflow 结论。
- **close 口径**：`sink.close()`/save 计入 write，可能在最后 `BATCH_END` 之后发出，由 `PIPELINE_END` 折叠。
- **嵌套写出**：LOAD_REF / streaming flush 在 loader·compute 窗内会扣回外层；stage 之和 ≈ 墙钟（容差内），不是严格相等。
- **兼容面**：业务 sink 输出内容不应因观测改变；数字（归因）会变更——这是预期。
- **依赖**：memory 路径需要可选 `psutil`；无则拒绝该配置，不静默空 peak。

## Viz

`run_stats.json` 可与 `viz_snapshot.json` **同目录旁路**存放；**禁止**把完整 run_stats 嵌入 snapshot 图契约。见 [可视化工具](scalim-viz.md)。

scalim-viz 会在导入目录/回放时**可选**读取 sibling `run_stats.json`（schema 必须为 `scalim_run_stats/v1`），用左侧 **Run Stats** 面板展示 `meta.profile` / `stages_total` / `nodes[]` / loaders；未知 schema 软忽略。

## Agent Skill

下游 / Agent 装配请优先加载：[`agentdev/skills/scalim-run-stats/SKILL.md`](repo:agentdev/skills/scalim-run-stats/SKILL.md?ref)。

下游升级卡（Before/After）：[`agentdev/skills/scalim-public-api/references/upgrades/2026-08-08-run-stats-low-drift-and-write-attribution.md`](repo:agentdev/skills/scalim-public-api/references/upgrades/2026-08-08-run-stats-low-drift-and-write-attribution.md?ref)。
