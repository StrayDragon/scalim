# 2026-08-08: run-stats-low-drift-and-write-attribution

## 变更摘要

新增低漂移自我观测面（`scalim_run_stats/v1` + `ObservabilityProfile` + workflow `nodes[]`），并修正现代 sink 路径上的 `stages.write` 归因（含嵌套写出扣回与 `sink.close()` 计入 write）。

| 项 | 说明 |
|----|------|
| Added | `scalim.ob.presets.profiles.build_observability_profile` / `ObservabilityProfile` |
| Added | `scalim.ob.presets.run_stats.WorkflowStatsAccumulator` / `write_run_stats_sibling` |
| Added | 高影响观测选项程序化启用时 `UserWarning`（指向 bench） |
| Behavior | 订阅 `STAGE_SPAN` 时 column/streaming sink I/O 与 `sink.close()` 计入 `write`；嵌在 loader/compute 窗内扣回外层 |
| Unchanged | 默认可不装配任何 observer；YAML 仍无 `observability.*` authoring surface |
| Unchanged | 业务 sink 输出内容不应因 lite 观测改变（可对拍 CSV/行哈希） |

规范引用:
- `llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/`
- `llmanspec/changes/archive/2026-08-08-c55-stage-write-attribution/`
- `llmanspec/specs/observability-run-stats/spec.toon`
- `llmanspec/specs/performance-observability/spec.toon`（r1001 / r1002）

人类文档: `docs/doc/viz/run-stats.md`  
Agent skill: `agentdev/skills/scalim-run-stats/SKILL.md`

---

## 如何判断是否受影响

```text
PerformanceObserver|RelationObserver
stages\.write|write_duration|STAGE_SPAN
components=\[|ObserverManager\(
PIPELINE_START.*reset|workflow.*metrics
run_stats|ObservabilityProfile|build_observability_profile
```

若你用共享 Perf/Relation 末态当「全 workflow 结论」，或用 `write==0` 判断写出成本，需要按后文调整读数面。

---

## 按 API 调整

### A. 日常自我观测：改用 bench profile + `nodes[]`

**若使用:** 手搓 `PerformanceObserver` 做 workflow 多 demand 汇总。

**调整:** 装配 `ObservabilityProfile.BENCH`，结论读 `run_stats.nodes`（及聚合字段），不要只读共享 observer 末态。

Before:

```python
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver

perf = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
# runtime components=[perf]
# 错误：把 perf.metrics 当成整个 workflow 结论
```

After:

```python
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
# DemandRunRuntimeOptions(components=list(built["components"]))
# after workflow/demand run:
stats = built["handles"]["accum"].build_run_stats(meta=built["meta"])
_ = stats["nodes"]  # 每 demand pipeline 快照
write_run_stats_sibling("/path/to/evidence-or-viz-run", stats)
```

### B. write 阶段：停止用「假零」下结论

**若使用:** `stage_metrics.write_duration` / `stages_total.write` 判断写出是否瓶颈。

**调整:** 在订阅 `STAGE_SPAN` 的路径上，现代 sink 写出后 write 应可 `> 0`；嵌套 flush 不会再把同一 I/O 完整双计进 loader/compute。`sink.close()` 计入 write，可能在最后 `BATCH_END` 之后折叠进 metrics。

### C. 高影响面：接受警告并优先 bench

**若使用:** `RelationObserver(enabled=True)`、`include_field_compute_top_n>0`、`VizObserverConfig(trace_enabled=True)` / `payload_policy="full"`。

**调整:** 构造时会 `UserWarning` 并提示 bench；生产/对拍默认改用 `ObservabilityProfile.BENCH`。memory / `BENCH_PLUS` 需要 psutil，否则 fail-fast。

### D. Viz：旁路文件，勿嵌入 snapshot

**若使用:** 把性能汇总塞进 `viz_snapshot.json`。

**调整:** 使用 `write_run_stats_sibling`；snapshot 图契约保持稳定。

---

## 验证建议

1. baseline vs bench：同输入 CSV/行内容哈希相等。
2. workflow：`len(stats["nodes"])` 对齐实际 pipeline 数；首节点 loaders 在第二段之后仍非空。
3. 有真实写出时：`stages_total.write > 0`（或 Perf `write_duration > 0`）。
4. 打开 debug/relation：应看到指向 bench 的警告。

更完整粘贴片段见 `docs/doc/viz/run-stats.md` 与 `agentdev/skills/scalim-run-stats/references/task-assemble-and-compare.md`。
