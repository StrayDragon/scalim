# region imports

from typing import Any, Dict, List, Optional, Union

from ...vendor.compact import StrEnum
from ..report_formats import ConsoleJsonlReportFormat
from .performance import PerformanceConfig, PerformanceObserver
from .relations import RelationConfig, RelationObserver
from .run_stats import (
    WorkflowStatsAccumulator,
    require_psutil_for_memory,
    warn_high_impact_observability,
)
from .stage_memory import StageMemoryConfig, StageMemoryObserver
from .viz import VizObserverConfig

# endregion


class ObservabilityProfile(StrEnum):
    BASELINE = "baseline"
    BENCH = "bench"
    BENCH_PLUS = "bench_plus"
    DEBUG = "debug"


# `wire`/`meta` 用的稳定字符串别名(`builtin` `str` 值).
PROFILE_BASELINE = ObservabilityProfile.BASELINE.value
PROFILE_BENCH = ObservabilityProfile.BENCH.value
PROFILE_BENCH_PLUS = ObservabilityProfile.BENCH_PLUS.value
PROFILE_DEBUG = ObservabilityProfile.DEBUG.value


def _coerce_profile(name):
    # type: (Union[ObservabilityProfile, str, None]) -> ObservabilityProfile
    if isinstance(name, ObservabilityProfile):
        return name
    raw = str(name or ObservabilityProfile.BASELINE).strip().lower()
    try:
        return ObservabilityProfile(raw)
    except ValueError:
        raise ValueError("未知可观测性 profile: {!r}".format(name))


def build_observability_profile(
    name,  # type: Union[ObservabilityProfile, str]
    sampling_interval=1,  # type: int
    include_memory=False,  # type: bool
    viz_output_dir=None,  # type: Optional[str]
    persist_batches=True,  # type: bool
):
    # type: (...) -> Dict[str, Any]
    """按具名低漂移 `profile` 组装 `observer` 组件.

    返回含键 `name`/`components`/`handles`/`viz_config`/`meta` 的 `dict`.
    `name` 接受 `ObservabilityProfile` 或 `builtin` `str`(经 `Enum` `SSOT` 归一).
    """
    profile = _coerce_profile(name)
    name_s = profile.value
    components = []  # type: List[Any]
    handles = {
        "accum": None,
        "perf": None,
        "stage_memory": None,
        "relation": None,
    }  # type: Dict[str, Any]
    viz_config = None  # type: Optional[VizObserverConfig]
    meta = {"profile": name_s, "sampling_interval": int(sampling_interval)}

    if profile == ObservabilityProfile.BASELINE:
        return {
            "name": name_s,
            "components": components,
            "handles": handles,
            "viz_config": None,
            "meta": meta,
        }

    # `bench_plus` 始终采样 `memory`;`debug`/`bench` 仅当 `include_memory=True`
    sample_rss = bool(include_memory) or profile == ObservabilityProfile.BENCH_PLUS
    if sample_rss:
        require_psutil_for_memory("profile={}".format(name_s))

    accum = WorkflowStatsAccumulator(sample_rss=sample_rss, persist_batches=bool(persist_batches))
    components.append(accum)
    handles["accum"] = accum

    if profile == ObservabilityProfile.DEBUG:
        warn_high_impact_observability("debug_profile")
        perf = PerformanceObserver(
            config=PerformanceConfig(
                metrics={"duration", "memory"} if sample_rss else {"duration"},
                sampling_interval=max(1, int(sampling_interval)),
                report_format="none",
                include_loader_stats=True,
                include_field_compute_top_n=20,
                include_advisor_hints=True,
            )
        )
        rel = RelationObserver(
            config=RelationConfig(
                enabled=True,
                sampling_rate=0.05,
                max_samples=2000,
                report_format="none",
                include_details=True,
            )
        )
        components.extend([perf, rel])
        handles["perf"] = perf
        handles["relation"] = rel
        if viz_output_dir:
            viz_config = VizObserverConfig(
                output_dir=str(viz_output_dir),
                trace_enabled=False,
                payload_policy="summary",
                append=False,
                run_name="scalim-bench-debug",
                env="dev",
            )
        if sample_rss:
            sm = StageMemoryObserver(
                config=StageMemoryConfig(
                    enabled=True,
                    sampling_interval=max(1, int(sampling_interval)),
                    report_format=ConsoleJsonlReportFormat.NONE,
                )
            )
            components.append(sm)
            handles["stage_memory"] = sm
    elif profile == ObservabilityProfile.BENCH_PLUS:
        perf = PerformanceObserver(
            config=PerformanceConfig(
                metrics={"duration", "memory"} if sample_rss else {"duration"},
                sampling_interval=max(1, int(sampling_interval)),
                report_format="none",
                include_loader_stats=True,
            )
        )
        sm = StageMemoryObserver(
            config=StageMemoryConfig(
                enabled=True,
                sampling_interval=max(1, int(sampling_interval)),
                report_format=ConsoleJsonlReportFormat.NONE,
            )
        )
        components.extend([perf, sm])
        handles["perf"] = perf
        handles["stage_memory"] = sm
    else:  # `bench`
        metrics = {"duration", "memory"} if include_memory else {"duration"}
        if "memory" in metrics:
            require_psutil_for_memory("bench.include_memory")
        perf = PerformanceObserver(
            config=PerformanceConfig(
                metrics=metrics,
                sampling_interval=max(1, int(sampling_interval)),
                report_format="none",
                include_loader_top_n=15,
            )
        )
        components.append(perf)
        handles["perf"] = perf

    meta["collectors"] = [type(c).__name__ for c in components]
    return {
        "name": name_s,
        "components": components,
        "handles": handles,
        "viz_config": viz_config,
        "meta": meta,
    }


__all__ = (
    "ObservabilityProfile",
    "PROFILE_BASELINE",
    "PROFILE_BENCH",
    "PROFILE_BENCH_PLUS",
    "PROFILE_DEBUG",
    "build_observability_profile",
)
