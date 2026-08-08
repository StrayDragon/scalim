# Run Stats（低漂移自我观测）

??? note "适用读者"
    - 需要用证据判断 loader / compute / relation / 框架优化方向的开发者
    - 需要 workflow 多 demand 汇总、而非「最后一次 pipeline」末态指标的同学

## 原则

- **默认静默**：生产可不装配任何 observer（`components=[]`）。
- **bench 低漂移**：只订 lite 事件；墙钟税通常为个位数百分比量级（以本机合成矩阵为准）。
- **debug 显式且警告**：relation / field_compute top-N / viz 等高影响面会 `UserWarning`，并提示改用 bench。
- **workflow 用 `nodes[]`**：共享 observer 会在下一 `PIPELINE_START` reset；完整结论读 `run_stats.nodes`，不要只读 `PerformanceObserver` 末态。
- **write 归因**：现代 sink 路径的 `stages.write` 完整归因见后续 write-attribution 变更；在完成前勿用 `write==0` 下「写出很快」的结论。

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

## Viz

`run_stats.json` 可与 `viz_snapshot.json` **同目录旁路**存放；**禁止**把完整 run_stats 嵌入 snapshot 图契约。
