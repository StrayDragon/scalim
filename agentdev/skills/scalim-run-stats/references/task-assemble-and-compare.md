# 任务：装配 run_stats + baseline/bench 对拍

## 何时用

- 用户要判断 loader / compute / write / relation 热点
- 框架或业务 A/B 需要同一 schema 证据
- 怀疑 `stages.write == 0` 或 workflow 指标「突然变空」

## 装配面（选一）

| 入口 | 接线 |
|------|------|
| YAML demand `run(...)` | `DemandRunRuntimeOptions(components=built["components"])` |
| YAML workflow `run_workflow(...)` | 经 `WorkflowRunOptions(demand=DemandRunOptions(runtime=...))` 把同一 `built["components"]` 挂到 demand runtime（共享实例才能跨 demand 累加 `nodes[]`） |
| `ScalimEngine` | `ObserverManager(observers=built["components"])` |

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    run,
)
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
run(
    "path/to/demand.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        runtime=DemandRunRuntimeOptions(components=list(built["components"])),
    ),
)
stats = built["handles"]["accum"].build_run_stats(meta=built["meta"])
write_run_stats_sibling(".tmp/evidence/run_stats", stats)
```

## 对拍清单

1. 同输入跑 `BASELINE` 与 `BENCH`（或同 demand 开关 components）。
2. **输出等价**：CSV/行内容哈希相等（业务内容）；xlsx 仅作存在性/size 参考。
3. **墙钟税**：`(bench_wall / baseline_wall) - 1`；记录环境（勿把单次跑当 SLA）；大作业上税可能落入噪声。
4. **证据面**：`stats["schema"] == "scalim_run_stats/v1"`；workflow 看 `len(nodes)` 与各节点 `loaders`/`stages_total`。
5. **write**：有真实写出且订阅了 stage span 时，`stages_total.write`（或 Perf `write_duration`）应 `> 0`；检查 `notes.write_stage_attribution == "sink_path_timed"`。

更完整的默认选择与交付清单：见 [best-practices.md](best-practices.md)。

## 禁止事项

- 不要在 YAML 里写 `observability.*`（已迁出；legacy warning/ignore 或 fail-fast 视版本）。
- 不要把完整 run_stats 写进 `viz_snapshot.json`。
- 不要用 debug 做默认生产观测。
- 不要只打印共享 Perf 末态就宣称「全 workflow 结论」。

## 交叉文档

- 人类：`docs/doc/viz/run-stats.md`
- 最佳实践：`references/best-practices.md`
- Viz：`docs/doc/viz/scalim-viz.md`
- YAML 可观测边界：`docs/doc/yaml-dsl/user-guide.md` §3.7
- 下游升级卡：`agentdev/skills/scalim-public-api/references/upgrades/2026-08-08-run-stats-low-drift-and-write-attribution.md`
- 本地合成矩阵（可选）：`.tmp/obs-demo/README.md`
