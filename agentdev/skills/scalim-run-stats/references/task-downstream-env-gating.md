# 下游环境门控：生产静默 vs 开发服观测

面向 Agent：装配下游（含 vendored `libs/scalim`）时的**默认策略**。不替代 `best-practices.md` 的读数规则。

## 硬门控

| 环境 | 开关习惯 | 观测策略 |
|------|----------|----------|
| **正式 / 生产** | 不设或 `SCALIM_DEBUG=0` | **`components=[]`**（或 `ObservabilityProfile.BASELINE`）。**禁止**默认挂 Perf / run_stats / StageMemory / Relation。零观测税。 |
| **开发服 / 对拍 / bench** | `SCALIM_DEBUG=1` 或显式 BenchSession | 用 Scalim 内置 presets：`build_observability_profile(...)`。可假定已装 **`psutil`**（memory / `BENCH_PLUS` / 内置 `StageMemoryObserver`）。 |
| **短窗深挖** | 显式 DEBUG + 跑完关掉 | `ObservabilityProfile.DEBUG`；接受 `UserWarning` 与高税；不要当生产默认。 |

**原则**：正式非 DEBUG 路径 MUST NOT「顺带」走进 memory 采样、stats 落盘、relation、field_compute top-N。门控放在业务入口（env / session），不要靠「忘了装 psutil」来静默降级。

## 推荐装配骨架

```python
import os
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.run_stats import write_run_stats_sibling

def resolve_obs_components(run_dir, *, debug=None, purpose="bench", include_memory=None):
    if debug is None:
        debug = os.environ.get("SCALIM_DEBUG", "0") == "1"
    if not debug and purpose == "baseline":
        return [], None  # 生产默认

    # 开发服：可假定 psutil；要 memory 时显式打开（缺失则 fail-fast，勿吞）
    if include_memory is None:
        include_memory = purpose in ("bench_plus", "debug")
    profile = {
        "baseline": ObservabilityProfile.BASELINE,
        "bench": ObservabilityProfile.BENCH,
        "bench_plus": ObservabilityProfile.BENCH_PLUS,
        "debug": ObservabilityProfile.DEBUG,
    }.get(purpose, ObservabilityProfile.BENCH)

    built = build_observability_profile(
        profile,
        include_memory=bool(include_memory),
    )
    return list(built["components"]), built
```

生产入口：

```python
components, _ = resolve_obs_components(run_dir, debug=False, purpose="baseline")
# DemandRunRuntimeOptions(components=components)  → []
```

开发 / bench 入口：

```python
components, built = resolve_obs_components(run_dir, debug=True, purpose="bench", include_memory=True)
# ... run ...
if built and built["handles"].get("accum") is not None:
    stats = built["handles"]["accum"].build_run_stats(meta=built["meta"])
    write_run_stats_sibling(run_dir, stats)
```

## psutil

- **开发服 / CI bench**：SHOULD 安装可选依赖 `psutil`；`include_memory=True` / `BENCH_PLUS` / 内置 stage memory 才可用。
- **生产非 DEBUG**：不装配 memory 观测 → **不需要**为观测装 psutil。
- 显式要了 memory 却无 psutil：上游 **fail-fast**（`require_psutil_for_memory`）。Agent MUST NOT 建议「吞掉改空 peak」。

## 禁止再造平行栈

- 不要再维护与 `WorkflowStatsAccumulator` 平行的自研 run_stats 累加器（历史 `et_scalim_run_stats/v1` 应迁 `scalim_run_stats/v1`）。
- 落盘用 `write_run_stats_sibling`；业务 HTML/对拍报告可读该 JSON，勿改上游 schema 语义。
- 手动业务阶段打点（如入口 `mark("data_loaded")`）可留在下游小工具；**事件面**观测用内置 + 可选自定义 Observer。

## 交叉

- 自定义 Observer/Hook：`scalim-public-api/references/task-observer-hook-extension.md`
- Profile / 读数 / 对拍：`best-practices.md`、`task-assemble-and-compare.md`
- 人类长文：`docs/doc/viz/run-stats.md`
