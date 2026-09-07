from dataclasses import dataclass
from typing import Any

from typing_extensions import override

from ..._internal.utils.loader_result import LoaderResultPolicy, parse_loader_result_policy
from ...events import Event, EventType, parse_event_type
from ...events._event import now_ts
from ...events._events import LoaderCallEvent
from ...hooks import HookManager


@dataclass(frozen=True)
class HookRecordedEvent:
    event_type: EventType
    event: Event


class HookCaptureManager(HookManager):
    """用于“捕获 + 提交时回放”的 `HookManager` 适配器.

    该管理器会记录类型化的完整 `Event` 信封,但不会调用用户 `hook`.
    `hook.on_event(Event)` 会通过 `ObserverManager` 的捕获模式被记录,并在提交时回放.

    线程安全/生命周期约束:
    - 订阅发现基于 `source.hooks` 的快照;在一次 `run` 期间动态 `register/unregister hooks`
      属于不受支持用法(尤其在 `parallel_mode="adaptive"` 下,并发任务会各自创建捕获管理器).
    """

    _recorded_events: list[HookRecordedEvent]

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

    def drain_events(self) -> list[HookRecordedEvent]:
        if not self._recorded_events:
            return []
        events = list(self._recorded_events)
        self._recorded_events.clear()
        return [self._normalize_recorded_event(event) for event in events]

    def _normalize_recorded_event(self, recorded: HookRecordedEvent) -> HookRecordedEvent:
        event = recorded.event
        return HookRecordedEvent(
            event_type=parse_event_type(event.event_type),
            event=Event(
                event_type=parse_event_type(event.event_type),
                timestamp=event.timestamp,
                run_id=event.run_id,
                payload=event.payload,
                meta=dict(event.meta) if event.meta else {},
                seq=event.seq,
            ),
        )

    @override
    def emit_typed(self, event_type: EventType, event: Event) -> None:
        if not self._has_hooks:
            return
        if event_type not in self._typed_handlers_by_event_type:
            return
        self._recorded_events.append(HookRecordedEvent(event_type=event_type, event=event))

    @override
    def trigger_loader_call(
        self,
        loader_name: str,
        params: dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: int | None = None,
        cache_status: str | None = None,
        cache_scope: str | None = None,
        lookup_key_count: int | None = None,
        field_keys: list[str] | None = None,
        skipped_none_rows: int | None = None,
        chunk_offset: int | None = None,
        meta: dict[str, Any] | None = None,
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

        loader_payload = LoaderCallEvent(
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
            chunk_offset=chunk_offset,
        )
        envelope = Event(
            event_type=EventType.LOADER_CALL,
            timestamp=now_ts(),
            run_id="",
            payload=loader_payload,
            meta=dict(meta) if meta else {},
            seq=0,
        )
        self._recorded_events.append(HookRecordedEvent(event_type=EventType.LOADER_CALL, event=envelope))


__all__ = ("HookCaptureManager", "HookRecordedEvent")
