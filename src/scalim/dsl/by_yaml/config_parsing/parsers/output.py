from typing import Any, Dict, Optional

from ...schema_dsl.constants import (
    DEFAULT_PERF_REPORT_FORMAT,
    DEFAULT_PERF_SAMPLING_INTERVAL,
    DEFAULT_REL_LOG_TYPE_MISMATCH,
    DEFAULT_REL_REPORT_FORMAT,
    DEFAULT_RELATION_MAX_SAMPLES,
    DEFAULT_RELATION_SAMPLING_RATE,
)
from ...schema_dsl.models import (
    DEMAND_KEYS,
    LOGGING_KEYS,
    MEMORY_OPTIMIZATION_KEYS,
    OBSERVABILITY_KEYS,
    PERFORMANCE_KEYS,
    PERFORMANCE_REPORT_KEYS,
    PERFORMANCE_THRESHOLDS_KEYS,
    RELATION_REPORT_KEYS,
    RELATIONS_CONFIG_KEYS,
    ROW_GAP_KEYS,
    TRACE_KEYS,
    VIZ_KEYS,
    LoggingConfig,
    MemoryOptimizationConfig,
    ObservabilityConfig,
    PerformanceConfig,
    PerformanceReportConfig,
    PerformanceThresholdsConfig,
    RelationReportConfig,
    RelationsConfig,
    RowGapConfig,
    TraceConfig,
    VizConfig,
)
from .utils import list_or_none, mapping_or_none, str_or_none

_VIZ_EVENT_MODE_REMOVED_MESSAGE = "observability.viz.event_mode has been removed; use observability.viz.trace_enabled"


class VizEventModeRemovedError(ValueError):
    def __init__(self) -> None:
        super(VizEventModeRemovedError, self).__init__(_VIZ_EVENT_MODE_REMOVED_MESSAGE)


class ParserOutputMixin:
    def _parse_observability(self, raw: Dict[str, Any]) -> Optional[ObservabilityConfig]:
        observability_dict = mapping_or_none(raw.get(DEMAND_KEYS["observability"]))
        if observability_dict is None:
            return None

        logging_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["logging"]))
        logging_config = self._parse_logging_observability(logging_raw) if logging_raw is not None else None

        perf_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["performance"]))
        performance = self._parse_performance(perf_raw) if perf_raw is not None else None

        relations_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["relations"]))
        relations = self._parse_relations_observability(relations_raw) if relations_raw is not None else None

        viz_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["viz"]))
        viz = self._parse_viz(viz_raw) if viz_raw is not None else None

        trace_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["trace"]))
        trace = self._parse_trace_observability(trace_raw) if trace_raw is not None else None

        row_gap_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["row_gap"]))
        row_gap = self._parse_row_gap_observability(row_gap_raw) if row_gap_raw is not None else None

        memory_opt_raw = mapping_or_none(observability_dict.get(OBSERVABILITY_KEYS["memory_opt"]))
        memory_opt = self._parse_memory_opt_observability(memory_opt_raw) if memory_opt_raw is not None else None

        return ObservabilityConfig(
            logging=logging_config,
            performance=performance,
            relations=relations,
            viz=viz,
            trace=trace,
            row_gap=row_gap,
            memory_opt=memory_opt,
        )

    def _parse_logging_observability(self, logging_raw: Dict[str, Any]) -> LoggingConfig:
        enabled = bool(logging_raw.get(LOGGING_KEYS["enabled"], True))
        default_renderer = LoggingConfig().renderer
        renderer_raw = logging_raw.get(LOGGING_KEYS["renderer"])
        renderer = renderer_raw if isinstance(renderer_raw, str) else default_renderer
        renderer = (renderer or default_renderer).lower()
        if renderer not in ("pretty", "logger"):
            renderer = default_renderer
        return LoggingConfig(enabled=enabled, renderer=renderer)

    def _parse_trace_observability(self, trace_raw: Dict[str, Any]) -> TraceConfig:
        enabled = bool(trace_raw.get(TRACE_KEYS["enabled"], False))
        return TraceConfig(enabled=enabled)

    def _parse_row_gap_observability(self, row_gap_raw: Dict[str, Any]) -> RowGapConfig:
        enabled = bool(row_gap_raw.get(ROW_GAP_KEYS["enabled"], False))
        primary_loader_name = str(row_gap_raw.get(ROW_GAP_KEYS["primary_loader_name"], "primary_keys"))

        data_loader_raw = row_gap_raw.get(ROW_GAP_KEYS["data_loader_names"])
        data_loader_list = list_or_none(data_loader_raw)
        if data_loader_list is not None:
            data_loader_names = tuple(str(item) for item in data_loader_list)
        elif isinstance(data_loader_raw, str):
            data_loader_names = (data_loader_raw,)
        else:
            data_loader_names = RowGapConfig().data_loader_names

        sample_limit_raw = row_gap_raw.get(ROW_GAP_KEYS["sample_limit"], 5)
        try:
            sample_limit = int(sample_limit_raw)
        except (TypeError, ValueError):
            sample_limit = 5

        return RowGapConfig(
            enabled=enabled,
            primary_loader_name=primary_loader_name,
            data_loader_names=data_loader_names,
            sample_limit=sample_limit,
        )

    def _parse_memory_opt_observability(self, memory_opt_raw: Dict[str, Any]) -> MemoryOptimizationConfig:
        enabled = bool(memory_opt_raw.get(MEMORY_OPTIMIZATION_KEYS["enabled"], False))
        auto_report = bool(memory_opt_raw.get(MEMORY_OPTIMIZATION_KEYS["auto_report"], False))

        max_fields_raw = memory_opt_raw.get(MEMORY_OPTIMIZATION_KEYS["max_fields"], 0)
        try:
            max_fields = int(max_fields_raw)
        except (TypeError, ValueError):
            max_fields = 0

        return MemoryOptimizationConfig(
            enabled=enabled,
            auto_report=auto_report,
            max_fields=max_fields,
        )

    def _parse_viz(self, viz_raw: Dict[str, Any]) -> VizConfig:
        if VIZ_KEYS["enabled"] in viz_raw:
            enabled = bool(viz_raw.get(VIZ_KEYS["enabled"]))
        else:
            enabled = bool(
                viz_raw.get(VIZ_KEYS["output_dir"])
                or viz_raw.get(VIZ_KEYS["output_path"])
                or viz_raw.get(VIZ_KEYS["snapshot_path"])
                or viz_raw.get(VIZ_KEYS["trace_enabled"])
                or viz_raw.get(VIZ_KEYS["use_default_output_dir"])
            )
        output_dir = str_or_none(viz_raw.get(VIZ_KEYS["output_dir"]))
        output_path = str_or_none(viz_raw.get(VIZ_KEYS["output_path"]))
        snapshot_path = str_or_none(viz_raw.get(VIZ_KEYS["snapshot_path"]))
        append = bool(viz_raw.get(VIZ_KEYS["append"], False))
        if "event_mode" in viz_raw:
            raise VizEventModeRemovedError
        trace_enabled = bool(viz_raw.get(VIZ_KEYS["trace_enabled"], False))
        payload_policy = str(viz_raw.get(VIZ_KEYS["payload_policy"], "summary"))
        sample_size_raw = viz_raw.get(VIZ_KEYS["sample_size"], 5)
        try:
            sample_size = int(sample_size_raw)
        except (TypeError, ValueError):
            sample_size = 5
        run_name = str_or_none(viz_raw.get(VIZ_KEYS["run_name"]))
        env = str_or_none(viz_raw.get(VIZ_KEYS["env"]))
        use_default_output_dir = bool(viz_raw.get(VIZ_KEYS["use_default_output_dir"], False))

        return VizConfig(
            enabled=enabled,
            output_dir=output_dir,
            output_path=output_path,
            snapshot_path=snapshot_path,
            append=append,
            trace_enabled=trace_enabled,
            payload_policy=payload_policy,
            sample_size=sample_size,
            run_name=run_name,
            env=env,
            use_default_output_dir=use_default_output_dir,
        )

    def _parse_relations_observability(self, relations_raw: Dict[str, Any]) -> RelationsConfig:
        enabled = bool(relations_raw.get(RELATIONS_CONFIG_KEYS["enabled"], False))

        sampling_rate_raw = relations_raw.get(RELATIONS_CONFIG_KEYS["sampling_rate"], DEFAULT_RELATION_SAMPLING_RATE)
        try:
            sampling_rate = float(sampling_rate_raw)
        except (TypeError, ValueError):
            sampling_rate = DEFAULT_RELATION_SAMPLING_RATE

        log_type_mismatch = bool(relations_raw.get(RELATIONS_CONFIG_KEYS["log_type_mismatch"], DEFAULT_REL_LOG_TYPE_MISMATCH))

        max_samples_raw = relations_raw.get(RELATIONS_CONFIG_KEYS["max_samples"], DEFAULT_RELATION_MAX_SAMPLES)
        try:
            max_samples = int(max_samples_raw)
        except (TypeError, ValueError):
            max_samples = DEFAULT_RELATION_MAX_SAMPLES

        report = self._parse_relation_report(relations_raw.get(RELATIONS_CONFIG_KEYS["report"]))

        return RelationsConfig(
            enabled=enabled,
            sampling_rate=sampling_rate,
            log_type_mismatch=log_type_mismatch,
            max_samples=max_samples,
            report=report,
        )

    def _parse_relation_report(self, report_raw: object) -> Optional[RelationReportConfig]:
        report_dict = mapping_or_none(report_raw)
        if report_dict is None:
            return None
        return RelationReportConfig(
            format=str(report_dict.get(RELATION_REPORT_KEYS["format"], DEFAULT_REL_REPORT_FORMAT)),
            output=str_or_none(report_dict.get(RELATION_REPORT_KEYS["output"])),
        )

    def _parse_performance(self, perf_raw: Dict[str, Any]) -> PerformanceConfig:
        enabled = bool(perf_raw.get(PERFORMANCE_KEYS["enabled"], False))

        metrics_raw = perf_raw.get(PERFORMANCE_KEYS["metrics"])
        metrics_list = list_or_none(metrics_raw)
        if metrics_list is not None:
            metrics = tuple(str(item) for item in metrics_list)
        elif isinstance(metrics_raw, str):
            metrics = (metrics_raw,)
        else:
            metrics = PerformanceConfig().metrics

        sampling_raw = perf_raw.get(PERFORMANCE_KEYS["sampling_interval"], DEFAULT_PERF_SAMPLING_INTERVAL)
        try:
            sampling_interval = int(sampling_raw)
        except (TypeError, ValueError):
            sampling_interval = DEFAULT_PERF_SAMPLING_INTERVAL

        report = self._parse_performance_report(perf_raw.get(PERFORMANCE_KEYS["report"]))
        thresholds = self._parse_performance_thresholds(perf_raw.get(PERFORMANCE_KEYS["thresholds"]))

        return PerformanceConfig(
            enabled=enabled,
            metrics=metrics,
            sampling_interval=sampling_interval,
            report=report,
            thresholds=thresholds,
        )

    def _parse_performance_report(self, report_raw: object) -> Optional[PerformanceReportConfig]:
        report_dict = mapping_or_none(report_raw)
        if report_dict is None:
            return None
        return PerformanceReportConfig(
            format=str(report_dict.get(PERFORMANCE_REPORT_KEYS["format"], DEFAULT_PERF_REPORT_FORMAT)),
            output=str_or_none(report_dict.get(PERFORMANCE_REPORT_KEYS["output"])),
            include_details=bool(report_dict.get(PERFORMANCE_REPORT_KEYS["include_details"], False)),
        )

    def _parse_performance_thresholds(self, thresholds_raw: object) -> Optional[PerformanceThresholdsConfig]:
        thresholds_dict = mapping_or_none(thresholds_raw)
        if thresholds_dict is None:
            return None
        batch_duration_warn = thresholds_dict.get(PERFORMANCE_THRESHOLDS_KEYS["batch_duration_warn"])
        memory_increase_warn = thresholds_dict.get(PERFORMANCE_THRESHOLDS_KEYS["memory_increase_warn"])
        return PerformanceThresholdsConfig(
            batch_duration_warn=float(batch_duration_warn) if batch_duration_warn is not None else None,
            memory_increase_warn=float(memory_increase_warn) if memory_increase_warn is not None else None,
        )
