# ruff: noqa: T201
# region imports

import logging
from typing import Any

from ...events.events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowReleaseEvent,
    RowWriteEvent,
)
from ...vendor.literich import Panel, Table
from ..observer import EventDispatchObserver

# endregion

_LOGGER = logging.getLogger(__name__)


class LoggingObserver(EventDispatchObserver):
    """日志观察者 - 记录执行进度到日志系统"""

    logger: logging.Logger

    def __init__(self, logger: logging.Logger | None = None) -> None:
        if logger is None:
            logger = _LOGGER
        self.logger = logger

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        self.logger.info(
            "[管道] 启动 | 目标字段: %d 个, 批大小: %d",
            len(event.targets),
            event.batch_size,
        )

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        self.logger.info(
            "[管道] 完成 | 批次: %d, 耗时: %.2fs",
            event.total_batches,
            event.total_duration,
        )

    def on_batch_start(self, event: BatchStartEvent) -> None:
        self.logger.info(
            "[批次 %d] 开始 | 记录数: %d",
            event.batch_num,
            len(event.row_ids),
        )

    def on_batch_end(self, event: BatchEndEvent) -> None:
        self.logger.info(
            "[批次 %d] 完成 | 耗时: %.2fs",
            event.batch_num,
            event.duration,
        )

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        loader_result: Any = event.result
        try:
            result_size = len(loader_result)
        except (TypeError, AttributeError):
            result_size = 0
        cache_note = ""
        if event.cache_status:
            cache_note = f" | cache: {event.cache_status}"
            if event.field_keys:
                cache_note += " fields: {}".format(",".join(event.field_keys))
        self.logger.info(
            "  [加载] %s | 返回: %d 条, 耗时: %.2fs%s",
            event.loader_name,
            result_size,
            event.duration,
            cache_note,
        )

    def on_field_compute(self, event: FieldComputeEvent) -> None:
        self.logger.debug(
            "  [计算] %s | row_id=%s, 结果=%s",
            event.field_key,
            event.row_id,
            event.result,
        )

    def on_error(self, event: ErrorEvent) -> None:
        self.logger.error("[错误] %s", str(event.error))
        if event.context:
            for key, ctx_value in event.context.items():
                self.logger.error("  %s: %s", key, ctx_value)

    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        self.logger.warning(
            "[诊断] %s | source=%s field=%s row_id=%s lookup_key=%r",
            event.message,
            event.source_id,
            event.field_id,
            event.row_id,
            event.lookup_key,
        )

    def on_field_slim(self, event: FieldSlimEvent) -> None:
        self.logger.debug("  [瘦身] 字段 %s | 原因: %s", event.field_key, event.reason)

    def on_row_write(self, event: RowWriteEvent) -> None:
        self.logger.debug("  [写入] 行 row_id=%s | 字段数: %d", event.row_id, event.field_count)

    def on_row_release(self, event: RowReleaseEvent) -> None:
        self.logger.debug(
            "  [释放] 行 row_id=%s | 释放: %d, 保留: %d",
            event.row_id,
            len(event.released_fields),
            len(event.retained_fields),
        )

    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        self.logger.debug("  [瘦身] Loader %s | 原始键数: %d", event.loader_name, event.original_keys)

    def on_column_write(self, event: ColumnWriteEvent) -> None:
        self.logger.debug("  [写入] 列 %s | 行数: %d", event.field_key, event.row_count)


class PrettyLoggingObserver(EventDispatchObserver):
    _loader_stats: list[dict[str, Any]]
    _total_rows: int

    def __init__(self) -> None:
        self._loader_stats = []
        self._total_rows = 0

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        content = f"目标字段: {len(event.targets):4d}    批大小: {event.batch_size:6d}"
        panel = Panel(content, title="Scalim Pipeline", width=50)
        print("\n" + panel.render())

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        _ = event
        content = f"批次数: {event.total_batches:4d}    总耗时: {event.total_duration:7.2f}s"
        panel = Panel(content, title="执行完成", width=50)
        print("\n" + panel.render())

        if self._loader_stats:
            table = Table("数据加载统计")
            _ = table.add_column("Loader", min_width=20)
            _ = table.add_column("记录数", min_width=8, align="right")
            _ = table.add_column("耗时", min_width=10, align="right")

            for stat in self._loader_stats:
                _ = table.add_row(stat["name"], stat["count"], "{:.3f}s".format(stat["duration"]))

            print("\n" + table.render())

    def on_batch_start(self, event: BatchStartEvent) -> None:
        self._total_rows += len(event.row_ids)

    def on_batch_end(self, event: BatchEndEvent) -> None:
        elapsed = max(0.0, float(event.duration))
        bar_len = min(int(elapsed * 10), 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  批次 {event.batch_num:3d} │{bar}│ {elapsed:.2f}s")

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        result_count = 0
        try:
            result_count = len(event.result)  # type: ignore[arg-type]
        except TypeError:
            result_count = 0
        name = event.loader_name
        if event.cache_status:
            fields = ",".join(event.field_keys or [])
            if fields:
                name = f"{name} [cache:{event.cache_status} fields:{fields}]"
            else:
                name = f"{name} [cache:{event.cache_status}]"
        self._loader_stats.append(
            {
                "name": name,
                "count": result_count,
                "duration": event.duration,
            }
        )


__all__ = [
    "LoggingObserver",
    "PrettyLoggingObserver",
]
