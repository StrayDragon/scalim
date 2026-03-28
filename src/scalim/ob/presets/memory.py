# region imports

import logging
from typing import List, Set

from ...events._events import ColumnWriteEvent, FieldSlimEvent, LoaderSlimEvent, RowReleaseEvent, RowWriteEvent
from ...vendor.compact.typing_extensionsx import override
from ...vendor.literich import Table
from ..observer import EventDispatchObserver

# endregion

_LOGGER = logging.getLogger(__name__)


class MemoryOptimizationObserver(EventDispatchObserver):
    field_slim_events: List[FieldSlimEvent]
    row_write_events: List[RowWriteEvent]
    row_release_events: List[RowReleaseEvent]
    loader_slim_events: List[LoaderSlimEvent]
    column_write_events: List[ColumnWriteEvent]
    _logger: logging.Logger

    auto_report: bool
    max_fields: int

    def __init__(
        self,
        logger: logging.Logger = _LOGGER,
        *,
        auto_report: bool = False,
        max_fields: int = 0,
    ) -> None:
        self.field_slim_events = []
        self.row_write_events = []
        self.row_release_events = []
        self.loader_slim_events = []
        self.column_write_events = []
        self._logger = logger
        self.auto_report = auto_report
        self.max_fields = max(0, max_fields)

    def on_field_slim(self, event: FieldSlimEvent) -> None:
        self.field_slim_events.append(event)
        self._logger.debug("  [瘦身] %s | %s", event.field_key, event.reason)

    def on_row_write(self, event: RowWriteEvent) -> None:
        self.row_write_events.append(event)
        self._logger.debug("  [写入] 行 row_id=%s", event.row_id)

    def on_row_release(self, event: RowReleaseEvent) -> None:
        self.row_release_events.append(event)
        self._logger.debug("  [释放] 行 row_id=%s", event.row_id)

    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        self.loader_slim_events.append(event)
        self._logger.debug("  [瘦身] 加载器 %s", event.loader_name)

    def on_column_write(self, event: ColumnWriteEvent) -> None:
        self.column_write_events.append(event)
        self._logger.debug("  [列写入] %s | %d 行", event.field_key, event.row_count)

    def get_slimmed_fields(self) -> Set[str]:
        return {e.field_key for e in self.field_slim_events}

    def get_columns_written(self) -> Set[str]:
        return {e.field_key for e in self.column_write_events}

    def print_summary(self, max_fields: int = 0) -> None:
        slimmed_fields = self.get_slimmed_fields()
        columns_written = self.get_columns_written()

        summary = Table(title="内存优化统计 (FR022/FR023)", border_style="box")
        _ = summary.add_column("指标", min_width=14)
        _ = summary.add_column("数量", min_width=8, align="right")

        _ = summary.add_row("字段瘦身", str(len(self.field_slim_events)))
        _ = summary.add_row("行写入", str(len(self.row_write_events)))
        _ = summary.add_row("行释放", str(len(self.row_release_events)))
        _ = summary.add_row("列写入", str(len(self.column_write_events)))
        _ = summary.add_row("Loader 瘦身", str(len(self.loader_slim_events)))

        output_lines = ["\n" + summary.render()]

        if slimmed_fields:
            fields_list = sorted(slimmed_fields)
            if max_fields > 0 and len(fields_list) > max_fields:
                fields_list = fields_list[:max_fields]
                fields_list.append("... (+{} more)".format(len(slimmed_fields) - max_fields))
            output_lines.append("瘦身字段: " + ", ".join(fields_list))

        if columns_written:
            cols_list = sorted(columns_written)
            if max_fields > 0 and len(cols_list) > max_fields:
                cols_list = cols_list[:max_fields]
                cols_list.append("... (+{} more)".format(len(columns_written) - max_fields))
            output_lines.append("已写入列: " + ", ".join(cols_list))

        self._logger.info("\n".join(output_lines))

    def reset(self) -> None:
        self.field_slim_events.clear()
        self.row_write_events.clear()
        self.row_release_events.clear()
        self.loader_slim_events.clear()
        self.column_write_events.clear()

    @override
    def close(self) -> None:
        if self.auto_report:
            self.print_summary(max_fields=self.max_fields)


__all__ = [
    "MemoryOptimizationObserver",
]
