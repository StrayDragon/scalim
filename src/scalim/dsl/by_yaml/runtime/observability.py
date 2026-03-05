from typing import TYPE_CHECKING, List, Optional, Tuple

from ....execution.run_ir import ObservabilitySpec
from ....ob.observer import Observer
from ....ob.presets.execution_trace import ExecutionTraceObserver
from ....ob.presets.logs import LoggingObserver, PrettyLoggingObserver
from ....ob.presets.memory import MemoryOptimizationObserver
from ....ob.presets.performance import PerformanceConfig, PerformanceObserver, PerformanceThresholds
from ....ob.presets.relations import RelationConfig, RelationObserver
from ....ob.presets.row_gap import RowGapObserver
from ....ob.presets.viz import VizObserverConfig
from ..schema_dsl.models import (
    LoggingConfig,
    MemoryOptimizationConfig,
    ObservabilityConfig,
    PerformanceReportConfig,
    RelationReportConfig,
    RelationsConfig,
    RowGapConfig,
    TraceConfig,
    VizConfig,
)
from ..schema_dsl.models import PerformanceConfig as PerformanceConfigYaml

if TYPE_CHECKING:
    from ....typedefs import PerformanceReportFormat, RelationReportFormat


def _resolve_performance_report_options(
    report: Optional[PerformanceReportConfig],
    allowed_formats: Tuple[str, ...],
    default_format: str,
) -> Tuple[str, Optional[str], bool]:
    report_format = default_format
    output_path: Optional[str] = None
    include_details = False
    if report is not None:
        report_format = report.format or default_format
        output_path = report.output
        include_details = bool(report.include_details)

    report_format_literal = default_format
    if report_format in allowed_formats:
        report_format_literal = report_format
    return report_format_literal, output_path, include_details


def _create_performance_observer_from_config(
    observability: Optional[ObservabilityConfig],
) -> Optional[PerformanceObserver]:
    if observability is None or observability.performance is None:
        return None

    perf_config: PerformanceConfigYaml = observability.performance
    if not perf_config.enabled:
        return None
    metrics_set = set(perf_config.metrics) if perf_config.metrics else {"duration"}

    def _build_config(
        perf: PerformanceConfigYaml,
        report_format: str,
        output_path: Optional[str],
        *,
        include_details: bool,
    ) -> PerformanceConfig:
        thresholds = PerformanceThresholds()
        if perf.thresholds:
            thresholds = PerformanceThresholds(
                batch_duration_warn=perf.thresholds.batch_duration_warn,
                memory_increase_warn=perf.thresholds.memory_increase_warn,
            )

        report_format_literal: "PerformanceReportFormat" = "console"
        if report_format in ("console", "json", "csv", "none"):
            report_format_literal = report_format  # type: ignore[assignment]

        return PerformanceConfig(
            metrics=metrics_set,
            sampling_interval=perf.sampling_interval,
            report_format=report_format_literal,
            output_path=output_path,
            include_details=include_details,
            thresholds=thresholds,
        )

    report_format, output_path, include_details = _resolve_performance_report_options(
        perf_config.report,
        ("console", "json", "csv", "none"),
        "console",
    )
    observer_config = _build_config(perf_config, report_format, output_path, include_details=include_details)
    return PerformanceObserver(config=observer_config)


def _create_relation_observer_from_config(
    observability: Optional[ObservabilityConfig],
) -> Optional[RelationObserver]:
    if observability is None or observability.relations is None:
        return None

    rel_config: RelationsConfig = observability.relations
    if not rel_config.enabled:
        return None

    report_format = "console"
    output_path = None
    report: Optional[RelationReportConfig] = rel_config.report
    if report is not None:
        report_format = report.format or "console"
        output_path = report.output
    if report_format not in ("console", "json", "none"):
        report_format = "console"

    def _build_config(
        rel: RelationsConfig,
        report_format: str,
        output_path: Optional[str],
    ) -> RelationConfig:
        report_format_literal: "RelationReportFormat" = "console"
        if report_format in ("console", "json", "none"):
            report_format_literal = report_format  # type: ignore[assignment]

        return RelationConfig(
            enabled=rel.enabled,
            sampling_rate=rel.sampling_rate,
            log_type_mismatch=rel.log_type_mismatch,
            max_samples=rel.max_samples,
            report_format=report_format_literal,
            output_path=output_path,
        )

    observer_config = _build_config(rel_config, report_format, output_path)
    return RelationObserver(config=observer_config)


def _compile_viz_config_from_config(
    observability: Optional[ObservabilityConfig],
) -> Optional[VizObserverConfig]:
    if observability is None or observability.viz is None:
        return None

    viz_config: VizConfig = observability.viz
    if not viz_config.enabled:
        return None
    use_default_output_dir = viz_config.use_default_output_dir
    if viz_config.output_dir is None and viz_config.output_path is None and viz_config.snapshot_path is None:
        use_default_output_dir = True
    return VizObserverConfig(
        output_dir=viz_config.output_dir,
        output_path=viz_config.output_path,
        snapshot_path=viz_config.snapshot_path,
        trace_enabled=viz_config.trace_enabled,
        append=viz_config.append,
        use_default_output_dir=use_default_output_dir,
        payload_policy=viz_config.payload_policy,
        sample_size=viz_config.sample_size,
        run_name=viz_config.run_name,
        env=viz_config.env,
    )


def _create_trace_observer_from_config(observability: Optional[ObservabilityConfig]) -> Optional[ExecutionTraceObserver]:
    if observability is None or observability.trace is None:
        return None
    cfg: TraceConfig = observability.trace
    if not cfg.enabled:
        return None
    return ExecutionTraceObserver()


def _create_row_gap_observer_from_config(observability: Optional[ObservabilityConfig]) -> Optional[RowGapObserver]:
    if observability is None or observability.row_gap is None:
        return None
    cfg: RowGapConfig = observability.row_gap
    if not cfg.enabled:
        return None
    return RowGapObserver(
        primary_loader_name=cfg.primary_loader_name,
        data_loader_names=cfg.data_loader_names,
        sample_limit=cfg.sample_limit,
    )


def _create_memory_opt_observer_from_config(
    observability: Optional[ObservabilityConfig],
) -> Optional[MemoryOptimizationObserver]:
    if observability is None or observability.memory_opt is None:
        return None
    cfg: MemoryOptimizationConfig = observability.memory_opt
    if not cfg.enabled:
        return None
    return MemoryOptimizationObserver(auto_report=cfg.auto_report, max_fields=cfg.max_fields)


def _create_logging_observer_from_config(
    observability: Optional[ObservabilityConfig],
) -> Optional[Observer]:
    if observability is None or observability.logging is None:
        # 默认行为:除非显式启用日志,否则保持静默.
        return None
    cfg: LoggingConfig = observability.logging
    if not cfg.enabled:
        return None
    renderer = (cfg.renderer or "pretty").lower()
    if renderer == "logger":
        return LoggingObserver()
    if renderer == "pretty":
        return PrettyLoggingObserver()
    return PrettyLoggingObserver()


def compile_observability_spec(
    observability: Optional[ObservabilityConfig],
) -> Tuple[ObservabilitySpec, Tuple[Observer, ...]]:
    logging_observer = _create_logging_observer_from_config(observability)
    perf_observer = _create_performance_observer_from_config(observability)
    relation_observer = _create_relation_observer_from_config(observability)
    viz_config = _compile_viz_config_from_config(observability)
    trace_observer = _create_trace_observer_from_config(observability)
    row_gap_observer = _create_row_gap_observer_from_config(observability)
    memory_opt_observer = _create_memory_opt_observer_from_config(observability)

    observers: List[Observer] = []
    for observer in (
        logging_observer,
        perf_observer,
        relation_observer,
        trace_observer,
        row_gap_observer,
        memory_opt_observer,
    ):
        if observer is not None:
            observers.append(observer)

    return (
        ObservabilitySpec(
            fallback_logger_enabled=logging_observer is not None,
            viz_config=viz_config,
        ),
        tuple(observers),
    )


__all__ = [
    "compile_observability_spec",
]
