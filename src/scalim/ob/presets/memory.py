# region imports

import logging
from typing import List, Set

from ...events import Event
from ...events._events import ColumnWriteEvent, FieldSlimEvent, LoaderSlimEvent, RowReleaseEvent, RowWriteEvent
from ...vendor.compact.typing_extensionsx import override
from .._internal.console_report import emit_info
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

    def on_field_slim(self, event: Event) -> None:
        payload = event.payload
        self.field_slim_events.append(payload)
        self._logger.debug("  [瘦身] %s | %s", payload.field_key, payload.reason)

    def on_row_write(self, event: Event) -> None:
        payload = event.payload
        self.row_write_events.append(payload)
        self._logger.debug("  [写入] 行 row_id=%s", payload.row_id)

    def on_row_release(self, event: Event) -> None:
        payload = event.payload
        self.row_release_events.append(payload)
        self._logger.debug("  [释放] 行 row_id=%s", payload.row_id)

    def on_loader_slim(self, event: Event) -> None:
        payload = event.payload
        self.loader_slim_events.append(payload)
        self._logger.debug("  [瘦身] 加载器 %s", payload.loader_name)

    def on_column_write(self, event: Event) -> None:
        payload = event.payload
        self.column_write_events.append(payload)
        self._logger.debug("  [列写入] %s | %d 行", payload.field_key, payload.row_count)

    def get_slimmed_fields(self) -> Set[str]:
        return {e.field_key for e in self.field_slim_events}

    def get_columns_written(self) -> Set[str]:
        return {e.field_key for e in self.column_write_events}

    def print_summary(self, max_fields: int = 0) -> None:
        slimmed_fields = self.get_slimmed_fields()
        columns_written = self.get_columns_written()
        limit = int(max_fields) if max_fields > 0 else (int(self.max_fields) if self.max_fields > 0 else 20)

        emit_info(
            self._logger,
            "memory",
            "summary",
            field_slims=len(self.field_slim_events),
            row_writes=len(self.row_write_events),
            row_releases=len(self.row_release_events),
            column_writes=len(self.column_write_events),
            loader_slims=len(self.loader_slim_events),
        )

        if slimmed_fields:
            fields_list = sorted(slimmed_fields)
            showing_items = fields_list[:limit]
            remaining = int(len(fields_list) - len(showing_items))
            emit_info(
                self._logger,
                "memory",
                "slimmed_fields",
                total=len(fields_list),
                showing=len(showing_items),
                fields=",".join(showing_items),
                more=remaining if remaining > 0 else None,
            )

        if columns_written:
            cols_list = sorted(columns_written)
            showing_items = cols_list[:limit]
            remaining = int(len(cols_list) - len(showing_items))
            emit_info(
                self._logger,
                "memory",
                "columns_written",
                total=len(cols_list),
                showing=len(showing_items),
                fields=",".join(showing_items),
                more=remaining if remaining > 0 else None,
            )

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


__all__ = ("MemoryOptimizationObserver",)
