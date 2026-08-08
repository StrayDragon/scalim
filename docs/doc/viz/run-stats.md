# Run Stats（低漂移自我观测）

??? note "适用读者"
    - 需要用证据判断 loader / compute / relation / 框架优化方向的开发者
    - 需要 workflow 多 demand 汇总、而非「最后一次 pipeline」末态指标的同学

## 原则

- **默认静默**：生产可不装配任何 observer（`components=[]`）。
- **bench 低漂移**：只订 lite 事件；墙钟税通常为个位数百分比量级（以本机合成矩阵为准）。
- **debug 显式且警告**：relation / field_compute top-N / viz 等高影响面会 `UserWarning`，并提示改用 bench。
- **workflow 用 `nodes[]`**：共享 observer 会在下一 `PIPELINE_START` reset；完整结论读 `run_stats.nodes`，不要只读 `PerformanceObserver` 末态。
- **write 归因**：现代 sink 路径（column / streaming flush / `sink.close()`）在订阅 `STAGE_SPAN` 时计入 `stages.write`；若写出嵌在 loader/compute 计时窗内会扣回外层，避免双计。

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

## Viz

`run_stats.json` 可与 `viz_snapshot.json` **同目录旁路**存放；**禁止**把完整 run_stats 嵌入 snapshot 图契约。
