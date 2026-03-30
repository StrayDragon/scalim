# region imports

import logging
import time
import warnings
from collections.abc import Sized
from typing import Any, Callable, Dict, List, Optional, Set

from ..._internal.loggingx import format_kv, get_logger, prefix
from ...events import (
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_LOADER_CALL,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_STAGE_SPAN,
)
from ...events._events import (
    AdaptiveSchedulerDecisionEvent,
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    FieldComputeEvent,
    LoaderCallEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from ...typedefs import PerformanceReportFormat
from ...vendor.compact.importlibx import import_module
from ...vendor.dataclassesx import dataclass, field
from ..observer import EventDispatchObserver
from ..perf_metrics import AdaptiveSchedulerMetrics, CpuSample, MemorySample, PerformanceMetrics
from .performance_presentation import PerformancePresentationLayer

# endregion

_LOGGER = get_logger("performance")

PSUTIL_NOT_INSTALLED_WARNING_PREFIX = "未安装 `psutil`"
PSUTIL_METRICS_DISABLED_WARNING = PSUTIL_NOT_INSTALLED_WARNING_PREFIX + ", 已禁用以下指标: `{}`"


@dataclass
class PerformanceThresholds:
    batch_duration_warn: Optional[float] = None
    memory_increase_warn: Optional[float] = None


@dataclass
class PerformanceConfig:
    metrics: Set[str] = field(default_factory=lambda: {"duration"})
    """要收集的指标集合(例如 `duration`/`memory`/`cpu`)."""

    sampling_interval: int = 1
    """采样间隔(按批次计数;`1` 表示每批采样)."""

    report_format: PerformanceReportFormat = "console"
    """报告输出格式(例如 `console`/`json`/`csv`/`none`)."""

    output_path: Optional[str] = None
    """可选:报告输出路径(部分格式必需)."""

    include_details: bool = False
    """是否在报告中包含明细数据."""

    include_scheduler_decisions: bool = False
    """是否包含自适应调度器决策统计(需要订阅相应事件)."""

    thresholds: PerformanceThresholds = field(default_factory=PerformanceThresholds)
    """告警阈值配置."""

    logger: logging.Logger = field(default=_LOGGER)
    """用于输出报告/告警的 `logging.Logger`."""

    presentation: Optional["PerformancePresentationLayer"] = None
    """可选:展示层实现(用于输出报告)."""

    @classmethod
    def default(cls) -> "PerformanceConfig":
        return cls()

    @classmethod
    def full(cls) -> "PerformanceConfig":
        return cls(metrics={"duration", "memory", "cpu"}, include_details=True, include_scheduler_decisions=True)


class PerformanceObserver(EventDispatchObserver):
    config: PerformanceConfig
    event_types: Optional[Set[str]]
    metrics: PerformanceMetrics
    _has_psutil: bool
    _process: Any
    _current_batch_num: int
    _batch_stage_durations: Dict[int, Dict[str, float]]
    _on_threshold_exceeded: Optional[Callable[[str, Any], None]]
    _presentation: PerformancePresentationLayer

    def __init__(
        self,
        config: Optional[PerformanceConfig] = None,
        on_threshold_exceeded: Optional[Callable[[str, Any], None]] = None,
    ) -> None:
        if config is None:
            config = PerformanceConfig.default()
        self.config = config
        self.event_types = {
            EVENT_PIPELINE_START,
            EVENT_PIPELINE_END,
            EVENT_BATCH_START,
            EVENT_BATCH_END,
            EVENT_LOADER_CALL,
            EVENT_STAGE_SPAN,
        }
        if config.include_scheduler_decisions:
            self.event_types.add(EVENT_ADAPTIVE_SCHEDULER_DECISION)
        self.metrics = PerformanceMetrics()
        self._on_threshold_exceeded = on_threshold_exceeded
        self._presentation = config.presentation or PerformancePresentationLayer()

        self._has_psutil = False
        self._process = None
        self._current_batch_num = 0
        self._batch_stage_durations = {}

        self._init_resource_monitoring()

    def _init_resource_monitoring(self) -> None:
        needs_psutil = "memory" in self.config.metrics or "cpu" in self.config.metrics
        if not needs_psutil:
            return

        try:
            psutil = import_module("psutil")

            self._has_psutil = True
            self._process = psutil.Process()

            if "memory" in self.config.metrics:
                self.metrics.memory_samples = []
            if "cpu" in self.config.metrics:
                self.metrics.cpu_samples = []
                _ = self._process.cpu_percent()

        except ImportError:
            self._has_psutil = False
            disabled_metrics: List[str] = []
            if "memory" in self.config.metrics:
                disabled_metrics.append("memory")
            if "cpu" in self.config.metrics:
                disabled_metrics.append("cpu")
            if disabled_metrics:
                warnings.warn(
                    PSUTIL_METRICS_DISABLED_WARNING.format(", ".join(disabled_metrics)),
                    stacklevel=2,
                )

    def _get_memory_mb(self) -> Optional[float]:
        if not self._has_psutil or self._process is None:
            return None
        try:
            rss = self._process.memory_info().rss
            return rss / 1024 / 1024
        except (OSError, AttributeError):
            return None

    def _get_cpu_percent(self) -> Optional[float]:
        if not self._has_psutil or self._process is None:
            return None
        try:
            return self._process.cpu_percent()
        except (OSError, AttributeError):
            return None

    def _sample_memory(self, label: str) -> None:
        if self.metrics.memory_samples is None:
            return
        mem_mb = self._get_memory_mb()
        if mem_mb is not None:
            sample = MemorySample(timestamp=time.time(), rss_mb=mem_mb, label=label)
            self.metrics.memory_samples.append(sample)
            if self.metrics.peak_memory_mb is None or mem_mb > self.metrics.peak_memory_mb:
                self.metrics.peak_memory_mb = mem_mb

    def _sample_cpu(self, label: str) -> None:
        if self.metrics.cpu_samples is None:
            return
        cpu_pct = self._get_cpu_percent()
        if cpu_pct is not None:
            sample = CpuSample(timestamp=time.time(), percent=cpu_pct, label=label)
            self.metrics.cpu_samples.append(sample)

    def _check_thresholds(self, metric_name: str, value: Any) -> None:
        thresholds = self.config.thresholds
        exceeded = False
        msg = ""

        if metric_name == "batch_duration" and thresholds.batch_duration_warn is not None:
            if isinstance(value, (int, float)) and value > thresholds.batch_duration_warn:
                exceeded = True
                kv = format_kv(
                    batch_num=int(self._current_batch_num),
                    duration_s="{:.2f}".format(float(value)),
                    threshold_s="{:.2f}".format(float(thresholds.batch_duration_warn)),
                )
                msg = "批次耗时超阈值"
                if kv:
                    msg = "{} {}".format(msg, kv)

        elif (
            metric_name == "memory_increase"
            and thresholds.memory_increase_warn is not None
            and isinstance(value, (int, float))
            and value > thresholds.memory_increase_warn
        ):
            exceeded = True
            kv = format_kv(
                memory_increase_mb="{:.1f}".format(float(value)),
                threshold_mb="{:.1f}".format(float(thresholds.memory_increase_warn)),
            )
            msg = "内存增长超阈值"
            if kv:
                msg = "{} {}".format(msg, kv)

        if exceeded:
            self.config.logger.warning("%s%s", prefix("performance"), msg)
            if self._on_threshold_exceeded:
                self._on_threshold_exceeded(metric_name, value)

    def _get_batch_stage_entry(self, batch_num: int) -> Dict[str, float]:
        entry = self._batch_stage_durations.get(batch_num)
        if entry is None:
            entry = {"loader": 0.0, "compute": 0.0, "write": 0.0}
            self._batch_stage_durations[batch_num] = entry
        return entry

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        _ = event
        self.metrics = PerformanceMetrics()
        self._batch_stage_durations.clear()
        if "memory" in self.config.metrics and self._has_psutil:
            self.metrics.memory_samples = []
        if "cpu" in self.config.metrics and self._has_psutil:
            self.metrics.cpu_samples = []

        mem_mb = self._get_memory_mb()
        if mem_mb is not None:
            self.metrics.start_memory_mb = mem_mb
            self._sample_memory("pipeline_start")

        self._sample_cpu("pipeline_start")

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        self.metrics.total_duration = event.total_duration
        self.metrics.batch_count = event.total_batches

        mem_mb = self._get_memory_mb()
        if mem_mb is not None:
            self.metrics.end_memory_mb = mem_mb
            self._sample_memory("pipeline_end")

        self._sample_cpu("pipeline_end")

        self._check_thresholds("memory_increase", self.metrics.memory_increase_mb)

        self._output_report()

    def on_batch_start(self, event: BatchStartEvent) -> None:
        self._current_batch_num = event.batch_num
        _ = self._get_batch_stage_entry(event.batch_num)
        # `PerformanceMetrics.total_rows` 统计输入的 `row_ids`,用于低开销估算吞吐量.
        # 它可能与 `sink` 实际写出的行数不同.
        self.metrics.total_rows += len(event.row_ids)

    def on_batch_end(self, event: BatchEndEvent) -> None:
        self.metrics.batch_durations.append(event.duration)

        stage_entry = self._batch_stage_durations.pop(event.batch_num, {"loader": 0.0, "compute": 0.0, "write": 0.0})
        self.metrics.stage_metrics.loader_duration += stage_entry["loader"]
        self.metrics.stage_metrics.compute_duration += stage_entry["compute"]
        self.metrics.stage_metrics.write_duration += stage_entry["write"]

        should_sample = event.batch_num % self.config.sampling_interval == 0
        if should_sample:
            label = "batch_{}".format(event.batch_num)
            self._sample_memory(label)
            self._sample_cpu(label)

        self._check_thresholds("batch_duration", event.duration)

        if self.config.include_details and self.config.report_format != "none":
            mem_mb = self._get_memory_mb()
            cpu_pct = self._get_cpu_percent()
            parts = ["duration={:.2f}s".format(event.duration)]
            parts.append("loader={:.2f}s".format(stage_entry["loader"]))
            parts.append("compute={:.2f}s".format(stage_entry["compute"]))
            parts.append("write={:.2f}s".format(stage_entry["write"]))
            if mem_mb is not None:
                parts.append("memory={:.1f}MB".format(mem_mb))
            if cpu_pct is not None:
                parts.append("cpu={:.1f}%".format(cpu_pct))
            self.config.logger.info(
                "%s批次 %d | %s",
                prefix("performance"),
                event.batch_num,
                ", ".join(parts),
            )

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        stats = self.metrics.get_loader_stats(event.loader_name)
        result_count = len(event.result) if isinstance(event.result, Sized) else 0
        stats.record_call(event.duration, result_count, event.cache_status)

    def on_field_compute(self, event: FieldComputeEvent) -> None:
        _ = event

    def on_row_write(self, event: RowWriteEvent) -> None:
        _ = event

    def on_column_write(self, event: ColumnWriteEvent) -> None:
        _ = event

    def on_stage_span(self, event: StageSpanEvent) -> None:
        entry = self._get_batch_stage_entry(event.batch_num)
        if event.stage in entry:
            entry[event.stage] += max(0.0, event.duration)

    def on_adaptive_scheduler_decision(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        metrics = self.metrics.adaptive_scheduler
        if metrics is None:
            metrics = AdaptiveSchedulerMetrics()
            self.metrics.adaptive_scheduler = metrics
        metrics.record_decision(event)

    def _output_report(self) -> None:
        self._presentation.output_report(
            metrics=self.metrics,
            report_format=self.config.report_format,
            output_path=self.config.output_path,
            include_details=self.config.include_details,
            logger=self.config.logger,
        )

    def _write_json_report(self) -> None:
        self._presentation.write_json_report(
            metrics=self.metrics,
            output_path=self.config.output_path,
            logger=self.config.logger,
        )

    def _write_csv_report(self) -> None:
        self._presentation.write_csv_report(
            metrics=self.metrics,
            output_path=self.config.output_path,
            logger=self.config.logger,
        )

    def print_summary(self) -> None:
        for line in self._presentation.iter_console_lines(self.metrics, include_details=self.config.include_details):
            self.config.logger.info("%s", line)

    def get_metrics(self) -> PerformanceMetrics:
        return self.metrics

    def reset(self) -> None:
        self.metrics = PerformanceMetrics()
        if "memory" in self.config.metrics and self._has_psutil:
            self.metrics.memory_samples = []
        if "cpu" in self.config.metrics and self._has_psutil:
            self.metrics.cpu_samples = []
        self._batch_stage_durations.clear()


__all__ = [
    "PerformanceConfig",
    "PerformanceObserver",
    "PerformanceThresholds",
]
