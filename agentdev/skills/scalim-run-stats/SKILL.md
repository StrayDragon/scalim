---
name: scalim-run-stats
description: "装配 Scalim 低漂移自我观测：run_stats v1、ObservabilityProfile(baseline/bench/bench_plus/debug)、workflow nodes[]、write stage 归因、baseline↔bench 对拍与 run_stats.json 旁路。用于性能判断、框架 A/B、排查 stages.write 假零/共享 observer 假空；不要用于改 YAML 业务建模（那用 scalim-yaml-dsl）。"
---

# Scalim Run Stats（低漂移自我观测）

先识别任务，只读最少 reference：

- **最佳实践（默认先读）**：[references/best-practices.md](references/best-practices.md)
- 装配 profile / 对拍清单：[references/task-assemble-and-compare.md](references/task-assemble-and-compare.md)
- **下游环境门控（生产静默 / 开发服 psutil）**：[references/task-downstream-env-gating.md](references/task-downstream-env-gating.md)
- 人类完整说明（Why / ROI / 风险 / 粘贴片段）：`docs/doc/viz/run-stats.md`
- Viz 产物契约：`docs/doc/viz/scalim-viz.md`
- 下游升级卡：`agentdev/skills/scalim-public-api/references/upgrades/2026-08-08-run-stats-low-drift-and-write-attribution.md`
- 若任务是写/改 YAML DSL：改用 `agentdev/skills/scalim-yaml-dsl`
- 若任务是 EventType / Observer / Hook 二开适配：改用 `agentdev/skills/scalim-public-api`（扩展卡：`references/task-observer-hook-extension.md`）

## 硬规则

1. **默认静默**：生产 / 正式非 DEBUG 可不装配；`components=[]` / 不传 observers。**禁止**生产默认挂 memory / debug / relation。
2. **日常用 bench**：`ObservabilityProfile.BENCH`；debug / relation / field_compute top-N / viz_trace|full 会 warn，且观测税更高（本机 mid debug ~+40%）。
3. **workflow 结论读 `run_stats.nodes`**：禁止把共享 `PerformanceObserver`/`RelationObserver` 末态当成全 workflow 真相（它们会在 `PIPELINE_START` reset）。
4. **同一 lite 事件平面**：run_stats 只订已有 `EventType`；不要另开热路径 instrumentation。
5. **viz sibling**：`write_run_stats_sibling` → `run_stats.json`；**禁止**把完整 run_stats 嵌入 `viz_snapshot.json`。
6. **write 归因**：订阅 `STAGE_SPAN` 时现代 sink I/O（含 `sink.close()`）计入 `write`；嵌在 loader/compute 窗内会扣回。`notes.write_stage_attribution` 应为 `sink_path_timed`。
7. **memory**：显式请求 memory / `BENCH_PLUS` 时无 psutil → **fail-fast**，禁止静默空 peak。开发服 / bench **SHOULD** 装 `psutil`；生产非 DEBUG 不装配则无需为观测装它。
8. **对拍**：baseline vs bench 业务输出（CSV 行/内容哈希）MUST 不变；可变的是墙钟与 metrics。xlsx 字节不可靠。
9. **扩展**：优先 `components = profile + [MyObs()]`；继承用 `EventDispatchObserver` / `BaseHook`。细节见 public-api 扩展卡。

## 最小入口

```python
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
# wire built["components"] into DemandRunRuntimeOptions / ObserverManager / workflow demand options
# after run:
stats = built["handles"]["accum"].build_run_stats(meta=built["meta"])
write_run_stats_sibling("/path/to/viz-or-evidence-dir", stats)
```

## 输出给用户时

- 写清用了哪个 profile、是否含观测税、结论来自 `nodes[]` 还是单 pipeline 末态。
- 若建议开 debug：同时警告税与替代（bench）；引用 best-practices 表中的量级时标明「本机合成、非 SLA」（mid debug ~+40%）。
- 需要溯源/复现矩阵时指向 archive mvp：`llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/`。
- 脱敏：不要引用下游业务路径/库名到公开文档或 commit。
