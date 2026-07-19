from typing import Any, Dict, List, Optional

from ..._internal.utils.loader_result import LoaderResultPolicy, parse_loader_result_policy
from ...events import EventType, parse_event_type
from ...events._events import LoaderCallEvent
from ...hooks import HookManager
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class HookRecordedEvent:
    event_type: EventType
    payload: Any


class HookCaptureManager(HookManager):
    """用于“捕获 + 提交时回放”的 `HookManager` 适配器.

    该管理器会记录类型化的 `hook` 负载,但不会调用用户 `hook`.
    `hook.on_event(Event)` 会通过 `ObserverManager` 的捕获模式被记录,并在提交时回放.

    线程安全/生命周期约束:
    - 订阅发现基于 `source.hooks` 的快照;在一次 `run` 期间动态 `register/unregister hooks`
      属于不受支持用法(尤其在 `parallel_mode="adaptive"` 下,并发任务会各自创建捕获管理器).
    """

    _recorded_events: List[HookRecordedEvent]

    def __init__(self, source: HookManager) -> None:
        normalized_loader_result_policy = parse_loader_result_policy(str(source.loader_result_policy))
        super().__init__(
            enable_debugging=source.debug_mode,
            fallback_logger_enabled=source.fallback_logger_enabled,
            loader_result_policy=LoaderResultPolicy(normalized_loader_result_policy),
            loader_result_sample_size=source.loader_result_sample_size,
        )
        # 仅复用原始 `hook` 实例用于订阅发现;捕获模式下不进行分发调用.
        self.hooks.extend(source.hooks)
        self._rebuild_subscription_cache()
        self._recorded_events = []

    def drain_events(self) -> List[HookRecordedEvent]:
        if not self._recorded_events:
            return []
        events = list(self._recorded_events)
        self._recorded_events.clear()
        return [self._normalize_recorded_event(event) for event in events]

    def _normalize_recorded_event(self, event: HookRecordedEvent) -> HookRecordedEvent:
        return HookRecordedEvent(event_type=parse_event_type(event.event_type), payload=event.payload)

    @override
    def emit_typed(self, event_type: EventType, payload: Any) -> None:
        if not self._has_hooks:
            return
        if event_type not in self._typed_handlers_by_event_type:
            return
        self._recorded_events.append(HookRecordedEvent(event_type=event_type, payload=payload))

    @override
    def trigger_loader_call(
        self,
        loader_name: str,
        params: Dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: Optional[int] = None,
        cache_status: Optional[str] = None,
        cache_scope: Optional[str] = None,
        lookup_key_count: Optional[int] = None,
        field_keys: Optional[List[str]] = None,
        skipped_none_rows: Optional[int] = None,
    ) -> None:
        if not self._has_hooks:
            return
        if EventType.LOADER_CALL not in self._typed_handlers_by_event_type:
            return

        payload = result
        if self.loader_result_policy == "none":
            payload = None
        elif self.loader_result_policy == "summary":
            payload = self._summarize_result(result)
        elif self.loader_result_policy == "sample":
            payload = self._sample_result(result)

        event = LoaderCallEvent(
            loader_name=loader_name,
            params=params,
            result=payload,
            duration=duration,
            batch_num=batch_num,
            cache_status=cache_status,
            cache_scope=cache_scope,
            lookup_key_count=lookup_key_count,
            skipped_none_rows=skipped_none_rows,
            field_keys=field_keys,
        )
        self._recorded_events.append(HookRecordedEvent(event_type=EventType.LOADER_CALL, payload=event))


__all__ = ("HookCaptureManager", "HookRecordedEvent")
