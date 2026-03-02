# region imports

import csv
import logging
import time
import warnings
from collections.abc import Callable, Sized
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...events.catalog import (
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_LOADER_CALL,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_STAGE_SPAN,
)
from ...events.events import (
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
from ...vendor.literich import Table
from ..observer import EventDispatchObserver
from ..perf_metrics import AdaptiveSchedulerMetrics, CpuSample, MemorySample, PerformanceMetrics

# endregion

_LOGGER = logging.getLogger(__name__)


@dataclass
class PerformanceThresholds:
    batch_duration_warn: float | None = None
    memory_increase_warn: float | None = None


@dataclass
class PerformanceConfig:
    metrics: set[str] = field(default_factory=lambda: {"duration"})
    sampling_interval: int = 1
    report_format: PerformanceReportFormat = "console"
    output_path: str | None = None
    include_details: bool = False
    include_scheduler_decisions: bool = False
    thresholds: PerformanceThresholds = field(default_factory=PerformanceThresholds)
    logger: logging.Logger = field(default=_LOGGER)

    @classmethod
    def default(cls) -> "PerformanceConfig":
        return cls()

    @classmethod
    def full(cls) -> "PerformanceConfig":
        return cls(metrics={"duration", "memory", "cpu"}, include_details=True, include_scheduler_decisions=True)


class PerformanceObserver(EventDispatchObserver):
    config: PerformanceConfig
    event_types: set[str] | None
    metrics: PerformanceMetrics
    _has_psutil: bool
    _process: Any
    _current_batch_num: int
    _batch_stage_durations: dict[int, dict[str, float]]
    _on_threshold_exceeded: Callable[[str, Any], None] | None

    def __init__(
        self,
        config: PerformanceConfig | None = None,
        on_threshold_exceeded: Callable[[str, Any], None] | None = None,
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
            disabled_metrics: list[str] = []
            if "memory" in self.config.metrics:
                disabled_metrics.append("memory")
            if "cpu" in self.config.metrics:
                disabled_metrics.append("cpu")
            if disabled_metrics:
                warnings.warn(
                    "psutil not installed, {} metrics disabled".format(", ".join(disabled_metrics)),
                    stacklevel=2,
                )

    def _get_memory_mb(self) -> float | None:
        if not self._has_psutil or self._process is None:
            return None
        try:
            rss = self._process.memory_info().rss
            return rss / 1024 / 1024
        except (OSError, AttributeError):
            return None

    def _get_cpu_percent(self) -> float | None:
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
                msg = f"Batch {self._current_batch_num} duration {value:.2f}s exceeds threshold {thresholds.batch_duration_warn:.2f}s"

        elif (
            metric_name == "memory_increase"
            and thresholds.memory_increase_warn is not None
            and isinstance(value, (int, float))
            and value > thresholds.memory_increase_warn
        ):
            exceeded = True
            msg = f"Memory increase {value:.1f}MB exceeds threshold {thresholds.memory_increase_warn:.1f}MB"

        if exceeded:
            self.config.logger.warning("[PerformanceObserver] %s", msg)
            if self._on_threshold_exceeded:
                self._on_threshold_exceeded(metric_name, value)

    def _get_batch_stage_entry(self, batch_num: int) -> dict[str, float]:
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
        # `PerformanceMetrics.total_rows` 统计的是输入 `row_ids`,用于低开销的吞吐估算.
        # 它可能不同于输出端(`sink`)实际发出的行数.
        self.metrics.total_rows += len(event.row_ids)

    def on_batch_end(self, event: BatchEndEvent) -> None:
        self.metrics.batch_durations.append(event.duration)

        stage_entry = self._batch_stage_durations.pop(event.batch_num, {"loader": 0.0, "compute": 0.0, "write": 0.0})
        self.metrics.stage_metrics.loader_duration += stage_entry["loader"]
        self.metrics.stage_metrics.compute_duration += stage_entry["compute"]
        self.metrics.stage_metrics.write_duration += stage_entry["write"]

        should_sample = event.batch_num % self.config.sampling_interval == 0
        if should_sample:
            label = f"batch_{event.batch_num}"
            self._sample_memory(label)
            self._sample_cpu(label)

        self._check_thresholds("batch_duration", event.duration)

        if self.config.include_details and self.config.report_format != "none":
            mem_mb = self._get_memory_mb()
            cpu_pct = self._get_cpu_percent()
            parts = [f"duration={event.duration:.2f}s"]
            parts.append("loader={:.2f}s".format(stage_entry["loader"]))
            parts.append("compute={:.2f}s".format(stage_entry["compute"]))
            parts.append("write={:.2f}s".format(stage_entry["write"]))
            if mem_mb is not None:
                parts.append(f"memory={mem_mb:.1f}MB")
            if cpu_pct is not None:
                parts.append(f"cpu={cpu_pct:.1f}%")
            self.config.logger.info(
                "[PerformanceObserver] Batch %d | %s",
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
        fmt = self.config.report_format
        if fmt == "none":
            return

        if fmt == "console":
            self.print_summary()
        elif fmt == "json":
            self._write_json_report()
        elif fmt == "csv":
            self._write_csv_report()

    def _write_json_report(self) -> None:
        output_path = self.config.output_path
        if not output_path:
            self.config.logger.info("\n%s", self.metrics.to_json())
            return

        try:
            path = Path(output_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(self.metrics.to_json(), encoding="utf-8")
            self.config.logger.info("[PerformanceObserver] Report written to %s", output_path)
        except OSError as e:
            self.config.logger.warning("[PerformanceObserver] Failed to write report: %s", e)

    def _write_csv_report(self) -> None:
        output_path = self.config.output_path
        if not output_path:
            self.config.logger.warning("[PerformanceObserver] CSV output requires output_path")
            return

        try:
            rows = self.metrics.to_csv_rows()
            if not rows:
                return

            path = Path(output_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            self.config.logger.info("[PerformanceObserver] Report written to %s", output_path)
        except OSError as e:
            self.config.logger.warning("[PerformanceObserver] Failed to write report: %s", e)

    def print_summary(self) -> None:
        m = self.metrics

        summary_table = Table(title="Performance Summary", border_style="box")
        _ = summary_table.add_column("Metric", min_width=20)
        _ = summary_table.add_column("Value", min_width=15, align="right")

        _ = summary_table.add_row("Total Duration", f"{m.total_duration:.3f}s")
        _ = summary_table.add_row("Total Rows", str(m.total_rows))
        _ = summary_table.add_row("Throughput", f"{m.throughput:.1f} rows/s")
        _ = summary_table.add_row("Batch Count", str(m.batch_count))
        _ = summary_table.add_row("Avg Batch Duration", f"{m.avg_batch_duration:.4f}s")

        if m.peak_memory_mb is not None:
            _ = summary_table.add_row("Peak Memory", f"{m.peak_memory_mb:.1f} MB")
        if m.memory_increase_mb is not None:
            _ = summary_table.add_row("Memory Increase", f"{m.memory_increase_mb:.1f} MB")

        output_lines = ["\n" + summary_table.render()]

        stages = m.stage_metrics
        if stages.loader_duration > 0 or stages.compute_duration > 0 or stages.write_duration > 0:
            stage_table = Table(title="Stage Breakdown", border_style="box")
            _ = stage_table.add_column("Stage", min_width=12)
            _ = stage_table.add_column("Duration", min_width=12, align="right")
            _ = stage_table.add_column("Percent", min_width=10, align="right")

            total = stages.loader_duration + stages.compute_duration + stages.write_duration
            if total > 0:
                _ = stage_table.add_row(
                    "Loader",
                    f"{stages.loader_duration:.3f}s",
                    f"{100 * stages.loader_duration / total:.1f}%",
                )
                _ = stage_table.add_row(
                    "Compute",
                    f"{stages.compute_duration:.3f}s",
                    f"{100 * stages.compute_duration / total:.1f}%",
                )
                _ = stage_table.add_row(
                    "Write",
                    f"{stages.write_duration:.3f}s",
                    f"{100 * stages.write_duration / total:.1f}%",
                )
                output_lines.append(stage_table.render())

        if m.loader_stats and self.config.include_details:
            loader_table = Table(title="Loader Statistics", border_style="box")
            _ = loader_table.add_column("Loader", min_width=20)
            _ = loader_table.add_column("Calls", min_width=6, align="right")
            _ = loader_table.add_column("Records", min_width=8, align="right")
            _ = loader_table.add_column("Avg Time", min_width=10, align="right")

            for name, stats in m.loader_stats.items():
                _ = loader_table.add_row(
                    name,
                    str(stats.call_count),
                    str(stats.total_records),
                    f"{stats.avg_duration:.4f}s",
                )
            output_lines.append(loader_table.render())

        self.config.logger.info("\n".join(output_lines))

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
