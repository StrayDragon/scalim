import csv
import logging
from pathlib import Path
from typing import Optional

from ...vendor.literich import Table
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
            logger.info(self.render_summary(metrics, include_details=include_details))
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
            logger.info("[PerformanceObserver] 报告已写入: %s", output_path)
        except OSError as e:
            logger.warning("[PerformanceObserver] 写入报告失败: %s", e)

    def write_csv_report(
        self,
        *,
        metrics: PerformanceMetrics,
        output_path: Optional[str],
        logger: logging.Logger,
    ) -> None:
        if not output_path:
            logger.warning("[PerformanceObserver] `CSV` 输出需要提供 output_path")
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

            logger.info("[PerformanceObserver] 报告已写入: %s", output_path)
        except OSError as e:
            logger.warning("[PerformanceObserver] 写入报告失败: %s", e)

    def render_summary(self, metrics: PerformanceMetrics, *, include_details: bool) -> str:
        summary_table = Table(title="Performance Summary", border_style="box")
        _ = summary_table.add_column("Metric", min_width=20)
        _ = summary_table.add_column("Value", min_width=15, align="right")

        _ = summary_table.add_row("Total Duration", "{:.3f}s".format(metrics.total_duration))
        _ = summary_table.add_row("Input Rows (row_ids)", str(metrics.total_rows))
        _ = summary_table.add_row("Throughput (row_ids/s)", "{:.1f} rows/s".format(metrics.throughput))
        _ = summary_table.add_row("Batch Count", str(metrics.batch_count))
        _ = summary_table.add_row("Avg Batch Duration", "{:.4f}s".format(metrics.avg_batch_duration))

        if metrics.peak_memory_mb is not None:
            _ = summary_table.add_row("Peak Memory", "{:.1f} MB".format(metrics.peak_memory_mb))
        if metrics.memory_increase_mb is not None:
            _ = summary_table.add_row("Memory Increase", "{:.1f} MB".format(metrics.memory_increase_mb))

        output_lines = ["\n" + summary_table.render()]

        stages = metrics.stage_metrics
        if stages.loader_duration > 0 or stages.compute_duration > 0 or stages.write_duration > 0:
            stage_table = Table(title="Stage Breakdown", border_style="box")
            _ = stage_table.add_column("Stage", min_width=12)
            _ = stage_table.add_column("Duration", min_width=12, align="right")
            _ = stage_table.add_column("Percent", min_width=10, align="right")

            total = stages.loader_duration + stages.compute_duration + stages.write_duration
            if total > 0:
                _ = stage_table.add_row(
                    "Loader",
                    "{:.3f}s".format(stages.loader_duration),
                    "{:.1f}%".format(100 * stages.loader_duration / total),
                )
                _ = stage_table.add_row(
                    "Compute",
                    "{:.3f}s".format(stages.compute_duration),
                    "{:.1f}%".format(100 * stages.compute_duration / total),
                )
                _ = stage_table.add_row(
                    "Write",
                    "{:.3f}s".format(stages.write_duration),
                    "{:.1f}%".format(100 * stages.write_duration / total),
                )
                output_lines.append(stage_table.render())

        if metrics.loader_stats and include_details:
            loader_table = Table(title="Loader Statistics", border_style="box")
            _ = loader_table.add_column("Loader", min_width=20)
            _ = loader_table.add_column("Calls", min_width=6, align="right")
            _ = loader_table.add_column("Records", min_width=8, align="right")
            _ = loader_table.add_column("Avg Time", min_width=10, align="right")

            for name, stats in metrics.loader_stats.items():
                _ = loader_table.add_row(
                    name,
                    str(stats.call_count),
                    str(stats.total_records),
                    "{:.4f}s".format(stats.avg_duration),
                )
            output_lines.append(loader_table.render())

        return "\n".join(output_lines)


__all__ = ["PerformancePresentationLayer"]
