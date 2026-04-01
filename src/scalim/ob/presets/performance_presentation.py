import csv
import logging
from pathlib import Path
from typing import List, Optional

from ..._internal.loggingx import prefix
from .._internal.console_report import build_line, format_percent, format_seconds
from ..perf_metrics import PerformanceMetrics


class PerformancePresentationLayer:
    """性能指标展示/导出层."""

    def output_report(
        self,
        *,
        metrics: PerformanceMetrics,
        report_format: str,
        output_path: Optional[str],
        include_details: bool,
        logger: logging.Logger,
    ) -> None:
        if report_format == "none":
            return
        if report_format == "console":
            for line in self.iter_console_lines(metrics, include_details=include_details):
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

    def iter_console_lines(self, metrics: PerformanceMetrics, *, include_details: bool) -> List[str]:
        lines: List[str] = []

        peak_memory_mb = metrics.peak_memory_mb
        memory_increase_mb = metrics.memory_increase_mb

        lines.append(
            build_line(
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
        )

        stages = metrics.stage_metrics
        total_stage = float(stages.loader_duration) + float(stages.compute_duration) + float(stages.write_duration)
        if total_stage > 0:
            stage_items = [
                ("loader", float(stages.loader_duration)),
                ("compute", float(stages.compute_duration)),
                ("write", float(stages.write_duration)),
            ]
            for stage, duration in stage_items:
                if duration <= 0:
                    continue
                lines.append(
                    build_line(
                        "performance",
                        "stage",
                        stage=str(stage),
                        duration_s=format_seconds(duration, digits=3),
                        percent=format_percent(duration / total_stage, digits=1),
                    )
                )

        if metrics.loader_stats and include_details:
            for name in sorted(metrics.loader_stats.keys()):
                stats = metrics.loader_stats[name]
                lines.append(
                    build_line(
                        "performance",
                        "loader",
                        loader=str(name),
                        calls=int(stats.call_count),
                        records=int(stats.total_records),
                        avg_time_s=format_seconds(stats.avg_duration, digits=4),
                    )
                )

        return lines

    def render_summary(self, metrics: PerformanceMetrics, *, include_details: bool) -> str:
        return "\n".join(self.iter_console_lines(metrics, include_details=include_details))


__all__ = ("PerformancePresentationLayer",)
