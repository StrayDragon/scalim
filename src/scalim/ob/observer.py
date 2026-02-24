# region imports

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ..events.catalog import (
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_COLUMN_WRITE,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_ERROR,
    EVENT_FIELD_COMPUTE,
    EVENT_FIELD_SLIM,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_LOADER_SLIM,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_RELATION_LOOKUP,
    EVENT_ROW_RELEASE,
    EVENT_ROW_WRITE,
    EVENT_STAGE_SPAN,
)
from ..events.event import Event
from ..vendor.compact.typing_extensionsx import override

# endregion

_DISPATCH_MAP = {
    EVENT_PIPELINE_START: "on_pipeline_start",
    EVENT_PIPELINE_END: "on_pipeline_end",
    EVENT_BATCH_START: "on_batch_start",
    EVENT_BATCH_END: "on_batch_end",
    EVENT_LOADER_CALL: "on_loader_call",
    EVENT_LOADER_RETRY: "on_loader_retry",
    EVENT_FIELD_COMPUTE: "on_field_compute",
    EVENT_ERROR: "on_error",
    EVENT_DIAGNOSTIC_WARNING: "on_diagnostic_warning",
    EVENT_FIELD_SLIM: "on_field_slim",
    EVENT_ROW_WRITE: "on_row_write",
    EVENT_ROW_RELEASE: "on_row_release",
    EVENT_LOADER_SLIM: "on_loader_slim",
    EVENT_COLUMN_WRITE: "on_column_write",
    EVENT_RELATION_LOOKUP: "on_relation_lookup",
    EVENT_STAGE_SPAN: "on_stage_span",
    EVENT_ADAPTIVE_SCHEDULER_DECISION: "on_adaptive_scheduler_decision",
}


class Observer(ABC):
    """Observer plugin base class."""

    event_types: set[str] | None = None
    supports_unknown_event_types: bool = False

    def supports(self, event_type: str) -> bool:
        if self.event_types is None:
            return True
        return event_type in self.event_types

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Handle a unified event."""

    def close(self) -> None:  # noqa: B027
        """Optional cleanup hook."""


class EventDispatchObserver(Observer):
    """Dispatch events to typed handlers if defined."""

    dispatch_map: dict[str, str] = _DISPATCH_MAP
    _handler_cache: dict[str, Callable[[Any], Any] | None]

    @override
    def on_event(self, event: Event) -> None:
        try:
            handler_cache = self._handler_cache
        except AttributeError:
            handler_cache = {}
            self._handler_cache = handler_cache

        event_type = event.event_type
        if event_type not in handler_cache:
            handler_name = self.dispatch_map.get(event_type)
            if not handler_name:
                handler_cache[event_type] = None
                return
            resolved = getattr(self, handler_name, None)
            if resolved is None or not callable(resolved):
                handler_cache[event_type] = None
                return
            handler_cache[event_type] = resolved

        handler = handler_cache[event_type]
        if handler is None:
            return
        _ = handler(event.payload)


__all__ = [
    "EventDispatchObserver",
    "Observer",
]
