# region imports

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Set

from ..events import (
    Event,
    EventType,
)
from ..vendor.compact.typing_extensionsx import override

# endregion

_DISPATCH_MAP: Dict[EventType, str] = {
    EventType.PIPELINE_START: "on_pipeline_start",
    EventType.PIPELINE_END: "on_pipeline_end",
    EventType.BATCH_START: "on_batch_start",
    EventType.BATCH_END: "on_batch_end",
    EventType.LOADER_CALL: "on_loader_call",
    EventType.LOADER_RETRY: "on_loader_retry",
    EventType.FIELD_COMPUTE: "on_field_compute",
    EventType.ERROR: "on_error",
    EventType.DIAGNOSTIC_WARNING: "on_diagnostic_warning",
    EventType.FIELD_SLIM: "on_field_slim",
    EventType.ROW_WRITE: "on_row_write",
    EventType.ROW_RELEASE: "on_row_release",
    EventType.LOADER_SLIM: "on_loader_slim",
    EventType.COLUMN_WRITE: "on_column_write",
    EventType.RELATION_LOOKUP: "on_relation_lookup",
    EventType.STAGE_SPAN: "on_stage_span",
    EventType.OPERATOR_SPAN: "on_operator_span",
    EventType.ADAPTIVE_SCHEDULER_DECISION: "on_adaptive_scheduler_decision",
    EventType.OUTPUT_TARGET_END: "on_output_target_end",
}


class Observer(ABC):
    """观测器插件基类."""

    event_types: Optional[Set[EventType]] = None
    supports_unknown_event_types: bool = False

    def supports(self, event_type: EventType) -> bool:
        if self.event_types is None:
            return True
        return event_type in self.event_types

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """处理统一事件."""

    def close(self) -> None:  # noqa: B027
        """可选的清理钩子."""


class EventDispatchObserver(Observer):
    """将事件分发到已定义的类型化处理函数."""

    dispatch_map: Dict[EventType, str] = _DISPATCH_MAP
    _handler_cache: Dict[EventType, Optional[Callable[[Any], Any]]]

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
            resolved = getattr(self, handler_name, None)  # pragma: allow-dynattr dispatch: handler_name
            if resolved is None or not callable(resolved):
                handler_cache[event_type] = None
                return
            handler_cache[event_type] = resolved

        handler = handler_cache[event_type]
        if handler is None:
            return
        _ = handler(event)


__all__ = (
    "EventDispatchObserver",
    "Observer",
)
