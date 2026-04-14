import csv
import logging
import statistics
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from ..._internal.loggingx import prefix
from .._internal.console_report import build_line, format_percent, format_seconds
from ..perf_metrics import PerformanceMetrics
from ..structured_logging import emit_structured, is_jsonl_logging_installed

_ADVISOR_DOMINANCE_RATIO = 0.6
_ADVISOR_MIN_LOADER_CALLS = 10
_ADVISOR_LOW_CACHE_HIT_RATE_MAX = 0.2


class PerformancePresentationLayer:
    """性能指标展示/导出层."""

    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        if not sorted_values:
            return 0.0
        if p <= 0:
            return float(sorted_values[0])
        if p >= 1:
            return float(sorted_values[-1])
        n = len(sorted_values)
        idx = round(p * (n - 1))
        idx = min(max(0, idx), n - 1)
        return float(sorted_values[idx])

    def output_report(
        self,
        *,
        metrics: PerformanceMetrics,
        report_format: str,
        output_path: Optional[str],
        include_loader_stats: bool,
        include_loader_top_n: int,
        include_field_compute_top_n: int,
        include_advisor_hints: bool,
        logger: logging.Logger,
    ) -> None:
        if report_format == "none":
            return
        if report_format == "console":
            if is_jsonl_logging_installed():
                self._emit_structured_console_report(
                    metrics=metrics,
                    include_loader_stats=include_loader_stats,
                    include_loader_top_n=int(include_loader_top_n),
                    include_field_compute_top_n=int(include_field_compute_top_n),
                    include_advisor_hints=bool(include_advisor_hints),
                    logger=logger,
                )
                return
            for line in self.iter_console_lines(
                metrics,
                include_loader_stats=include_loader_stats,
                include_loader_top_n=int(include_loader_top_n),
                include_field_compute_top_n=int(include_field_compute_top_n),
                include_advisor_hints=bool(include_advisor_hints),
            ):
                logger.info("%s", line)
            return
        if report_format == "json":
            self.write_json_report(metrics=metrics, output_path=output_path, logger=logger)
            return
        if report_format == "csv":
            self.write_csv_report(metrics=metrics, output_path=output_path, logger=logger)

    def write_json_report(
        self,
        *,
        metrics: PerformanceMetrics,
        output_path: Optional[str],
        logger: logging.Logger,
    ) -> None:
        if not output_path:
            logger.info("\n%s", metrics.to_json())
            return

        try:
            path = Path(output_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(metrics.to_json(), encoding="utf-8")
            logger.info("%s报告已写入: %s", prefix("performance"), output_path)
        except OSError as e:
            logger.warning("%s写入报告失败: %s", prefix("performance"), e)

    def write_csv_report(
        self,
        *,
        metrics: PerformanceMetrics,
        output_path: Optional[str],
        logger: logging.Logger,
    ) -> None:
        if not output_path:
            logger.warning("%sCSV 输出需要提供 output_path", prefix("performance"))
            return

        try:
            rows = metrics.to_csv_rows()
            if not rows:
                return

            path = Path(output_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            logger.info("%s报告已写入: %s", prefix("performance"), output_path)
        except OSError as e:
            logger.warning("%s写入报告失败: %s", prefix("performance"), e)

    def _build_console_summary_line(self, metrics: PerformanceMetrics) -> str:
        peak_memory_mb = metrics.peak_memory_mb
        memory_increase_mb = metrics.memory_increase_mb
        return build_line(
            "performance",
            "summary",
            total_duration_s=format_seconds(metrics.total_duration, digits=3),
            total_rows=int(metrics.total_rows),
            throughput_rows_s="{:.1f}".format(float(metrics.throughput)),
            batch_count=int(metrics.batch_count),
            avg_batch_duration_s=format_seconds(metrics.avg_batch_duration, digits=4),
            peak_memory_mb="{:.1f}".format(float(peak_memory_mb)) if peak_memory_mb is not None else None,
            memory_increase_mb="{:.1f}".format(float(memory_increase_mb)) if memory_increase_mb is not None else None,
        )

    def _iter_stage_items(self, metrics: PerformanceMetrics) -> Iterator[Tuple[str, float, float]]:
        stages = metrics.stage_metrics
        total_stage = (
            float(stages.stream_duration) + float(stages.loader_duration) + float(stages.compute_duration) + float(stages.write_duration)
        )
        if total_stage <= 0:
            return

        stage_items = [
            ("stream", float(stages.stream_duration)),
            ("loader", float(stages.loader_duration)),
            ("compute", float(stages.compute_duration)),
            ("write", float(stages.write_duration)),
        ]
        for stage, duration in stage_items:
            if duration <= 0:
                continue
            yield str(stage), float(duration), float(duration / total_stage)

    def _iter_console_stage_lines(self, metrics: PerformanceMetrics) -> List[str]:
        lines: List[str] = []
        for stage, duration, percent in self._iter_stage_items(metrics):
            lines.append(
                build_line(
                    "performance",
                    "stage",
                    stage=str(stage),
                    duration_s=format_seconds(duration, digits=3),
                    percent=format_percent(percent, digits=1),
                )
            )
        return lines

    def _compute_loader_breakdown(self, metrics: PerformanceMetrics) -> Optional[Dict[str, float]]:
        if metrics.total_duration <= 0:
            return None

        stages = metrics.stage_metrics
        stream_s = float(stages.stream_duration)
        source_lookup_s = float(stages.loader_duration)
        compute_s = float(stages.compute_duration)
        write_s = float(stages.write_duration)
        overhead_s = float(metrics.total_duration) - (stream_s + source_lookup_s + compute_s + write_s)
        return {
            "stream_s": float(stream_s),
            "source_lookup_s": float(source_lookup_s),
            "compute_s": float(compute_s),
            "write_s": float(write_s),
            "untracked_overhead_s": float(max(0.0, overhead_s)),
        }

    def _build_console_loader_breakdown_line(self, metrics: PerformanceMetrics) -> Optional[str]:
        breakdown = self._compute_loader_breakdown(metrics)
        if not breakdown:
            return None
        return build_line(
            "performance",
            "loader_breakdown",
            stream_s=format_seconds(breakdown["stream_s"], digits=4),
            source_lookup_s=format_seconds(breakdown["source_lookup_s"], digits=4),
            compute_s=format_seconds(breakdown["compute_s"], digits=4),
            write_s=format_seconds(breakdown["write_s"], digits=4),
            untracked_overhead_s=format_seconds(breakdown["untracked_overhead_s"], digits=4),
        )

    def _compute_batch_stats(self, metrics: PerformanceMetrics) -> Optional[Dict[str, float]]:
        if not metrics.batch_durations:
            return None
        durations = sorted(float(x) for x in metrics.batch_durations)
        if not durations:
            return None
        stddev_s = float(statistics.pstdev(durations)) if len(durations) > 1 else 0.0
        return {
            "min_s": float(min(durations)),
            "max_s": float(max(durations)),
            "p50_s": float(self._percentile(durations, 0.5)),
            "p90_s": float(self._percentile(durations, 0.9)),
            "stddev_s": float(stddev_s),
        }

    def _build_console_batch_stats_line(self, metrics: PerformanceMetrics) -> Optional[str]:
        stats = self._compute_batch_stats(metrics)
        if not stats:
            return None
        return build_line(
            "performance",
            "batch_stats",
            batch_count=int(metrics.batch_count),
            min_s=format_seconds(stats["min_s"], digits=4),
            max_s=format_seconds(stats["max_s"], digits=4),
            p50_s=format_seconds(stats["p50_s"], digits=4),
            p90_s=format_seconds(stats["p90_s"], digits=4),
            stddev_s=format_seconds(stats["stddev_s"], digits=4),
        )

    def _iter_console_loader_top_lines(self, metrics: PerformanceMetrics, *, include_loader_top_n: int) -> List[str]:
        if not metrics.loader_stats or include_loader_top_n <= 0:
            return []

        items = sorted(
            metrics.loader_stats.values(),
            key=lambda s: (-float(s.total_duration), str(s.name)),
        )
        lines: List[str] = []
        for stats in items[: int(max(0, include_loader_top_n))]:
            lines.append(
                build_line(
                    "performance",
                    "loader_top",
                    loader=str(stats.name),
                    total_s=format_seconds(float(stats.total_duration), digits=4),
                    exec_calls=int(stats.exec_count),
                    calls=int(stats.call_count),
                    records=int(stats.total_records),
                    cache_hit_rate="{:.2f}".format(float(stats.cache_hit_rate)),
                )
            )
        return lines

    def _iter_console_loader_lines(self, metrics: PerformanceMetrics) -> List[str]:
        if not metrics.loader_stats:
            return []

        lines: List[str] = []
        for name in sorted(metrics.loader_stats.keys()):
            stats = metrics.loader_stats[name]
            durations = sorted(float(x) for x in stats.durations) if stats.durations else []
            p50_s = self._percentile(durations, 0.5) if durations else None
            p90_s = self._percentile(durations, 0.9) if durations else None
            lines.append(
                build_line(
                    "performance",
                    "loader",
                    loader=str(name),
                    total_s=format_seconds(float(stats.total_duration), digits=4),
                    exec_calls=int(stats.exec_count),
                    calls=int(stats.call_count),
                    records=int(stats.total_records),
                    avg_time_s=format_seconds(stats.avg_duration, digits=4),
                    p50_s=format_seconds(p50_s, digits=4) if p50_s is not None else None,
                    p90_s=format_seconds(p90_s, digits=4) if p90_s is not None else None,
                    cache_hit_rate="{:.2f}".format(float(stats.cache_hit_rate)),
                )
            )
        return lines

    def _iter_console_field_top_lines(self, metrics: PerformanceMetrics, *, include_field_compute_top_n: int) -> List[str]:
        if not metrics.field_compute_stats or include_field_compute_top_n <= 0:
            return []

        items = sorted(
            metrics.field_compute_stats.values(),
            key=lambda s: (-float(s.total_duration), str(s.field_key)),
        )
        lines: List[str] = []
        for stats in items[: int(max(0, include_field_compute_top_n))]:
            lines.append(
                build_line(
                    "performance",
                    "field_top",
                    field=str(stats.field_key),
                    total_s=format_seconds(float(stats.total_duration), digits=4),
                    calls=int(stats.call_count),
                    avg_duration_s=format_seconds(float(stats.avg_duration), digits=4),
                )
            )
        return lines

    def _iter_console_advisor_hint_lines(self, metrics: PerformanceMetrics) -> List[str]:
        return [build_line("performance", "advisor_hint", hint=str(h), severity=str(s)) for h, s in self._iter_advisor_hints(metrics)]

    def _emit_structured_summary(self, metrics: PerformanceMetrics, *, logger: logging.Logger) -> None:
        peak_memory_mb = metrics.peak_memory_mb
        memory_increase_mb = metrics.memory_increase_mb
        emit_structured(
            logger,
            level=logging.INFO,
            kind="performance.summary",
            message="performance.summary",
            fields={
                "total_duration_s": float(metrics.total_duration),
                "total_rows": int(metrics.total_rows),
                "throughput_rows_s": float(metrics.throughput),
                "batch_count": int(metrics.batch_count),
                "avg_batch_duration_s": float(metrics.avg_batch_duration),
                "peak_memory_mb": float(peak_memory_mb) if peak_memory_mb is not None else None,
                "memory_increase_mb": float(memory_increase_mb) if memory_increase_mb is not None else None,
            },
        )

    def _emit_structured_stage_lines(self, metrics: PerformanceMetrics, *, logger: logging.Logger) -> None:
        for stage, duration, percent in self._iter_stage_items(metrics):
            emit_structured(
                logger,
                level=logging.INFO,
                kind="performance.stage",
                message="performance.stage",
                fields={
                    "stage": str(stage),
                    "duration_s": float(duration),
                    "percent": float(percent),
                },
            )

    def _emit_structured_loader_breakdown(self, metrics: PerformanceMetrics, *, logger: logging.Logger) -> None:
        breakdown = self._compute_loader_breakdown(metrics)
        if not breakdown:
            return
        emit_structured(
            logger,
            level=logging.INFO,
            kind="performance.loader_breakdown",
            message="performance.loader_breakdown",
            fields=dict(breakdown),
        )

    def _emit_structured_batch_stats(self, metrics: PerformanceMetrics, *, logger: logging.Logger) -> None:
        stats = self._compute_batch_stats(metrics)
        if not stats:
            return
        fields = dict(stats)
        fields["batch_count"] = int(metrics.batch_count)
        emit_structured(
            logger,
            level=logging.INFO,
            kind="performance.batch_stats",
            message="performance.batch_stats",
            fields=fields,
        )

    def _emit_structured_loader_top(self, metrics: PerformanceMetrics, *, include_loader_top_n: int, logger: logging.Logger) -> None:
        if not metrics.loader_stats or include_loader_top_n <= 0:
            return

        items = sorted(
            metrics.loader_stats.values(),
            key=lambda s: (-float(s.total_duration), str(s.name)),
        )
        for stats in items[: int(max(0, include_loader_top_n))]:
            emit_structured(
                logger,
                level=logging.INFO,
                kind="performance.loader_top",
                message="performance.loader_top",
                fields={
                    "loader_name": str(stats.name),
                    "total_s": float(stats.total_duration),
                    "exec_calls": int(stats.exec_count),
                    "calls": int(stats.call_count),
                    "records": int(stats.total_records),
                    "cache_hit_rate": float(stats.cache_hit_rate),
                },
            )

    def _emit_structured_loader_lines(self, metrics: PerformanceMetrics, *, logger: logging.Logger) -> None:
        if not metrics.loader_stats:
            return

        for name in sorted(metrics.loader_stats.keys()):
            stats = metrics.loader_stats[name]
            durations = sorted(float(x) for x in stats.durations) if stats.durations else []
            p50_s = float(self._percentile(durations, 0.5)) if durations else None
            p90_s = float(self._percentile(durations, 0.9)) if durations else None
            emit_structured(
                logger,
                level=logging.INFO,
                kind="performance.loader",
                message="performance.loader",
                fields={
                    "loader_name": str(name),
                    "total_s": float(stats.total_duration),
                    "exec_calls": int(stats.exec_count),
                    "calls": int(stats.call_count),
                    "records": int(stats.total_records),
                    "p50_s": p50_s,
                    "p90_s": p90_s,
                    "cache_hit_rate": float(stats.cache_hit_rate),
                },
            )

    def _emit_structured_field_top(self, metrics: PerformanceMetrics, *, include_field_compute_top_n: int, logger: logging.Logger) -> None:
        if not metrics.field_compute_stats or include_field_compute_top_n <= 0:
            return

        items = sorted(
            metrics.field_compute_stats.values(),
            key=lambda s: (-float(s.total_duration), str(s.field_key)),
        )
        for stats in items[: int(max(0, include_field_compute_top_n))]:
            emit_structured(
                logger,
                level=logging.INFO,
                kind="performance.field_top",
                message="performance.field_top",
                fields={
                    "field": str(stats.field_key),
                    "total_s": float(stats.total_duration),
                    "calls": int(stats.call_count),
                    "avg_duration_s": float(stats.avg_duration),
                },
            )

    def _emit_structured_advisor_hints(self, metrics: PerformanceMetrics, *, logger: logging.Logger) -> None:
        for hint, severity in self._iter_advisor_hints(metrics):
            emit_structured(
                logger,
                level=logging.INFO,
                kind="performance.advisor_hint",
                message="performance.advisor_hint",
                fields={
                    "hint": str(hint),
                    "severity": str(severity),
                },
            )

    def iter_console_lines(
        self,
        metrics: PerformanceMetrics,
        *,
        include_loader_stats: bool,
        include_loader_top_n: int,
        include_field_compute_top_n: int,
        include_advisor_hints: bool,
    ) -> List[str]:
        lines = [self._build_console_summary_line(metrics)]
        lines.extend(self._iter_console_stage_lines(metrics))

        breakdown_line = self._build_console_loader_breakdown_line(metrics)
        if breakdown_line:
            lines.append(breakdown_line)

        batch_stats_line = self._build_console_batch_stats_line(metrics)
        if batch_stats_line:
            lines.append(batch_stats_line)

        lines.extend(self._iter_console_loader_top_lines(metrics, include_loader_top_n=int(include_loader_top_n)))
        if include_loader_stats:
            lines.extend(self._iter_console_loader_lines(metrics))
        lines.extend(self._iter_console_field_top_lines(metrics, include_field_compute_top_n=int(include_field_compute_top_n)))
        if include_advisor_hints:
            lines.extend(self._iter_console_advisor_hint_lines(metrics))
        return lines

    def render_summary(
        self,
        metrics: PerformanceMetrics,
        *,
        include_loader_stats: bool,
        include_loader_top_n: int,
        include_field_compute_top_n: int,
        include_advisor_hints: bool,
    ) -> str:
        return "\n".join(
            self.iter_console_lines(
                metrics,
                include_loader_stats=include_loader_stats,
                include_loader_top_n=int(include_loader_top_n),
                include_field_compute_top_n=int(include_field_compute_top_n),
                include_advisor_hints=bool(include_advisor_hints),
            )
        )

    def _emit_structured_console_report(
        self,
        *,
        metrics: PerformanceMetrics,
        include_loader_stats: bool,
        include_loader_top_n: int,
        include_field_compute_top_n: int,
        include_advisor_hints: bool,
        logger: logging.Logger,
    ) -> None:
        self._emit_structured_summary(metrics, logger=logger)
        self._emit_structured_stage_lines(metrics, logger=logger)
        self._emit_structured_loader_breakdown(metrics, logger=logger)
        self._emit_structured_batch_stats(metrics, logger=logger)
        self._emit_structured_loader_top(metrics, include_loader_top_n=int(include_loader_top_n), logger=logger)
        if include_loader_stats:
            self._emit_structured_loader_lines(metrics, logger=logger)
        self._emit_structured_field_top(metrics, include_field_compute_top_n=int(include_field_compute_top_n), logger=logger)
        if include_advisor_hints:
            self._emit_structured_advisor_hints(metrics, logger=logger)

    def _iter_advisor_hints(self, metrics: PerformanceMetrics) -> Iterable[Tuple[str, str]]:
        stages = metrics.stage_metrics
        total_stage = (
            float(stages.stream_duration) + float(stages.loader_duration) + float(stages.compute_duration) + float(stages.write_duration)
        )
        if total_stage <= 0:
            return ()

        ratios = {
            "stream": float(stages.stream_duration) / total_stage if total_stage else 0.0,
            "lookup": float(stages.loader_duration) / total_stage if total_stage else 0.0,
            "compute": float(stages.compute_duration) / total_stage if total_stage else 0.0,
            "write": float(stages.write_duration) / total_stage if total_stage else 0.0,
        }

        hints: List[Tuple[str, str]] = []
        if ratios["stream"] >= _ADVISOR_DOMINANCE_RATIO:
            hints.append(("streaming-dominated: prioritize DB/streaming, not source lookup tuning", "info"))
        if ratios["lookup"] >= _ADVISOR_DOMINANCE_RATIO:
            hints.append(("lookup-dominated: consider preload_forever or reducing per-batch lookup fanout", "info"))
        if ratios["compute"] >= _ADVISOR_DOMINANCE_RATIO:
            hints.append(("compute-bound: batch_size tuning may have limited benefit; optimize compute operators", "info"))
        if ratios["write"] >= _ADVISOR_DOMINANCE_RATIO:
            hints.append(("write-bound: check sink/export performance and I/O bandwidth", "info"))

        if metrics.loader_stats:
            low_hit = sorted(
                (
                    s
                    for s in metrics.loader_stats.values()
                    if s.call_count >= _ADVISOR_MIN_LOADER_CALLS and s.cache_hit_rate <= _ADVISOR_LOW_CACHE_HIT_RATE_MAX
                ),
                key=lambda s: float(s.cache_hit_rate),
            )
            if low_hit:
                s0 = low_hit[0]
                hints.append(("low cache hit-rate for loader '{}': consider preload_forever or cache key strategy".format(s0.name), "warn"))

        return hints[:3]


__all__ = ("PerformancePresentationLayer",)
