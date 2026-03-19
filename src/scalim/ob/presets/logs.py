# ruff: noqa: T201
# region imports

import logging
from typing import Any, Dict, List, Optional

from ..._internal.loggingx import format_kv, get_logger, prefix
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

_LOGGER = get_logger("pipeline")

LOGGING_OBSERVER_LOADER_SLIM_LOG = prefix("pipeline") + "加载器瘦身"
LOGGING_OBSERVER_COLUMN_WRITE_LOG = prefix("pipeline") + "写入列"


class LoggingObserver(EventDispatchObserver):
    """日志观察者:将执行进度写入日志系统"""

    logger: logging.Logger

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        if logger is None:
            logger = _LOGGER
        self.logger = logger

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        batch_size_text = "all" if event.batch_size is None else str(event.batch_size)
        kv = format_kv(target_fields=len(event.targets), batch_size=batch_size_text)
        self.logger.info("%s管道启动 %s", prefix("pipeline"), kv)

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        kv = format_kv(batches=event.total_batches, total_duration_s="{:.2f}".format(float(event.total_duration)))
        self.logger.info("%s管道完成 %s", prefix("pipeline"), kv)

    def on_batch_start(self, event: BatchStartEvent) -> None:
        kv = format_kv(batch_num=event.batch_num, row_count=len(event.row_ids))
        self.logger.info("%s批次开始 %s", prefix("pipeline"), kv)

    def on_batch_end(self, event: BatchEndEvent) -> None:
        kv = format_kv(batch_num=event.batch_num, duration_s="{:.2f}".format(float(event.duration)))
        self.logger.info("%s批次完成 %s", prefix("pipeline"), kv)

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        loader_result: Any = event.result
        try:
            result_size = len(loader_result)
        except (TypeError, AttributeError):
            result_size = 0
        cache_status = None
        cache_fields = None
        if event.cache_status:
            if event.field_keys:
                cache_fields = ",".join(event.field_keys)
            cache_status = str(event.cache_status)
        kv = format_kv(
            loader_name=event.loader_name,
            result_count=int(result_size),
            duration_s="{:.2f}".format(float(event.duration)),
            cache_status=cache_status,
            cache_fields=cache_fields,
        )
        self.logger.info("%s加载 %s", prefix("pipeline"), kv)

    def on_field_compute(self, event: FieldComputeEvent) -> None:
        kv = format_kv(field_key=event.field_key, row_id=event.row_id, result=event.result)
        self.logger.debug("%s计算 %s", prefix("pipeline"), kv)

    def on_error(self, event: ErrorEvent) -> None:
        self.logger.error("%s错误: %s", prefix("pipeline"), str(event.error))
        if event.context:
            for key, ctx_value in event.context.items():
                self.logger.error("%s  %s: %s", prefix("pipeline"), key, ctx_value)

    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        kv = format_kv(
            message=event.message,
            source_id=event.source_id,
            field_id=event.field_id,
            row_id=event.row_id,
            lookup_key=event.lookup_key,
        )
        self.logger.warning("%s诊断警告 %s", prefix("pipeline"), kv)

    def on_field_slim(self, event: FieldSlimEvent) -> None:
        kv = format_kv(field_key=event.field_key, reason=event.reason)
        self.logger.debug("%s字段瘦身 %s", prefix("pipeline"), kv)

    def on_row_write(self, event: RowWriteEvent) -> None:
        kv = format_kv(row_id=event.row_id, field_count=event.field_count)
        self.logger.debug("%s写入行 %s", prefix("pipeline"), kv)

    def on_row_release(self, event: RowReleaseEvent) -> None:
        kv = format_kv(
            row_id=event.row_id,
            released_count=len(event.released_fields),
            retained_count=len(event.retained_fields),
        )
        self.logger.debug("%s释放行 %s", prefix("pipeline"), kv)

    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        kv = format_kv(loader_name=event.loader_name, original_keys=event.original_keys)
        self.logger.debug("%s加载器瘦身 %s", prefix("pipeline"), kv)

    def on_column_write(self, event: ColumnWriteEvent) -> None:
        kv = format_kv(field_key=event.field_key, row_count=event.row_count)
        self.logger.debug("%s写入列 %s", prefix("pipeline"), kv)


class PrettyLoggingObserver(EventDispatchObserver):
    _loader_stats: List[Dict[str, Any]]
    _total_rows: int

    def __init__(self) -> None:
        self._loader_stats = []
        self._total_rows = 0

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        batch_size_text = "all" if event.batch_size is None else str(event.batch_size)
        content = "目标字段: {:4d}    批大小: {:>6}".format(len(event.targets), batch_size_text)
        panel = Panel(content, title="Scalim Pipeline", width=50)
        print("\n" + panel.render())

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        _ = event
        content = "批次数: {:4d}    总耗时: {:7.2f}s".format(event.total_batches, event.total_duration)
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
        print("  批次 {:3d} │{}│ {:.2f}s".format(event.batch_num, bar, elapsed))

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
                name = "{} [cache:{} fields:{}]".format(name, event.cache_status, fields)
            else:
                name = "{} [cache:{}]".format(name, event.cache_status)
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
