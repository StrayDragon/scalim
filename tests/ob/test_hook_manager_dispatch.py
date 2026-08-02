import time

import pytest

from scalim.events import Event, EventType
from scalim.hooks import BaseHook, HookManager
from scalim.hooks import HookDispatchStrategy


def test_base_hook_on_event_is_noop() -> None:
    hook = BaseHook()
    hook.on_event(Event(event_type="x", timestamp=time.time(), run_id="r", payload=None))


class _PartialTypedHook(object):
    def __init__(self) -> None:
        self.pipeline_start_events = []

    def on_pipeline_start(self, event) -> None:  # type: ignore[no-untyped-def]
        self.pipeline_start_events.append(event)


def test_hook_manager_partial_hook_subscription_inference() -> None:
    hook = _PartialTypedHook()
    manager = HookManager()
    manager.register(hook)  # type: ignore[arg-type]

    manager.trigger_pipeline_start(targets=["x"], batch_size=1)
    assert len(hook.pipeline_start_events) == 1


def test_hook_manager_wants_diagnostic_warning_when_empty_and_fallback_enabled() -> None:
    manager = HookManager(fallback_logger_enabled=True)
    assert manager.wants(EventType.DIAGNOSTIC_WARNING) is False


def test_hook_manager_emit_typed_returns_when_non_catalog_event_type() -> None:
    manager = HookManager()
    manager.register(BaseHook())

    manager.emit_typed("non_catalog", Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="", payload=None, meta={}, seq=0))


class _GetattrNoneHook(object):
    def __init__(self) -> None:
        self.called = False

    def on_pipeline_start(self, event) -> None:  # type: ignore[no-untyped-def]
        self.called = True

    def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
        if name == "on_pipeline_start":
            return None
        return object.__getattribute__(self, name)


def test_hook_manager_emit_typed_skips_hooks_with_missing_handler() -> None:
    hook = _GetattrNoneHook()
    manager = HookManager()
    manager.register(hook)  # type: ignore[arg-type]

    manager.emit_typed(
        EventType.PIPELINE_START, Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="", payload=None, meta={}, seq=0)
    )
    assert hook.called is False


def test_hook_manager_emit_typed_does_not_use_getattr_after_cache_build() -> None:
    class _CountingGetattrHook(BaseHook):
        def __init__(self) -> None:
            self.getattr_calls = 0
            self.called = 0

        def on_pipeline_start(self, event) -> None:  # type: ignore[override]
            _ = event
            self.called += 1

        def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
            if name in {"getattr_calls", "called"}:
                return object.__getattribute__(self, name)
            if name == "on_pipeline_start":
                calls = object.__getattribute__(self, "getattr_calls")
                object.__setattr__(self, "getattr_calls", calls + 1)
            return object.__getattribute__(self, name)

    hook = _CountingGetattrHook()
    manager = HookManager()
    manager.register(hook)
    initial_calls = hook.getattr_calls

    manager.emit_typed(
        EventType.PIPELINE_START, Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="", payload=None, meta={}, seq=0)
    )

    assert hook.called == 1
    assert hook.getattr_calls == initial_calls


def test_hook_manager_event_types_filters_typed_subscriptions() -> None:
    class _FilteredTypedHook(BaseHook):
        event_types = {EventType.PIPELINE_END}

        def __init__(self) -> None:
            self.called = False

        def on_pipeline_start(self, event) -> None:  # type: ignore[override]
            _ = event
            self.called = True

    hook = _FilteredTypedHook()
    manager = HookManager()
    manager.register(hook)

    manager.trigger_pipeline_start(targets=["x"], batch_size=1)
    assert hook.called is False


def test_hook_manager_register_rejects_invalid_event_types_type() -> None:
    class _InvalidEventTypesHook(BaseHook):
        event_types = ["x"]  # type: ignore[assignment]

    manager = HookManager()
    with pytest.raises(TypeError, match="event_types"):
        manager.register(_InvalidEventTypesHook())


def test_hook_manager_register_rejects_event_types_with_non_str_entries() -> None:
    class _InvalidEventTypesHook(BaseHook):
        event_types = {EventType.PIPELINE_START, 123}  # type: ignore[assignment]

    manager = HookManager()
    with pytest.raises(TypeError, match="contain only EventType"):
        manager.register(_InvalidEventTypesHook())


def test_hook_manager_emit_typed_skips_when_handler_missing_and_event_types_is_set() -> None:
    class _GetattrNoneTypedHook(object):
        event_types = {EventType.PIPELINE_START}

        def __init__(self) -> None:
            self.called = False

        def on_pipeline_start(self, event) -> None:  # type: ignore[no-untyped-def]
            _ = event
            self.called = True

        def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
            if name == "on_pipeline_start":
                return None
            return object.__getattribute__(self, name)

    hook = _GetattrNoneTypedHook()
    manager = HookManager()
    manager.register(hook)  # type: ignore[arg-type]

    manager.trigger_pipeline_start(targets=["x"], batch_size=1)
    assert hook.called is False


class _SubsetOnEventHook(BaseHook):
    event_types = {EventType.PIPELINE_START}

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        _ = event


def test_hook_manager_emit_on_event_returns_when_unsubscribed() -> None:
    manager = HookManager()
    manager.register(_SubsetOnEventHook())

    manager.emit_on_event(Event(event_type=EventType.PIPELINE_END, timestamp=time.time(), run_id="r", payload=None))


def test_hook_manager_emit_on_event_skips_hooks_missing_on_event_handler() -> None:
    class _GetattrNoneOnEventHook(BaseHook):
        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

        def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
            if name == "on_event":
                return None
            return object.__getattribute__(self, name)

    manager = HookManager()
    manager.register(_GetattrNoneOnEventHook())

    manager.emit_on_event(Event(event_type=EventType.PIPELINE_START, timestamp=time.time(), run_id="r", payload=None))


def test_hook_manager_triggers_return_when_empty() -> None:
    manager = HookManager()
    manager.trigger_pipeline_start(targets=["x"], batch_size=1)
    manager.trigger_pipeline_end(total_batches=0, total_duration=0.0)
    manager.trigger_batch_start(batch_num=1, row_ids=[1])
    manager.trigger_batch_end(batch_num=1, duration=0.0)
    manager.trigger_field_compute(field_key="f", row_id=1, dependencies={}, result=None)
    manager.trigger_field_slim(field_key="f", reason="x", batch_num=1, remaining_fields=0)
    manager.trigger_row_write(row_id=1, field_count=1, batch_num=1, row_index=0)
    manager.trigger_row_release(row_id=1, released_fields=[], retained_fields=[], batch_num=1)
    manager.trigger_loader_slim(loader_name="l", original_keys=1, extracted_fields=[], batch_num=1)
    manager.trigger_column_write(field_key="f", row_count=1, batch_num=1)


class _CaptureManyHook(BaseHook):
    def __init__(self) -> None:
        self.events = []

    def on_pipeline_end(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.PIPELINE_END, event))

    def on_batch_start(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.BATCH_START, event))

    def on_batch_end(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.BATCH_END, event))

    def on_loader_call(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.LOADER_CALL, event))

    def on_field_compute(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.FIELD_COMPUTE, event))

    def on_error(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.ERROR, event))

    def on_diagnostic_warning(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.DIAGNOSTIC_WARNING, event))

    def on_field_slim(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.FIELD_SLIM, event))

    def on_row_write(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.ROW_WRITE, event))

    def on_row_release(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.ROW_RELEASE, event))

    def on_loader_slim(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.LOADER_SLIM, event))

    def on_column_write(self, event) -> None:  # type: ignore[override]
        self.events.append((EventType.COLUMN_WRITE, event))


def test_hook_manager_triggers_dispatch_and_sampling_paths() -> None:
    hook = _CaptureManyHook()
    manager = HookManager()
    manager.register(hook)

    manager.trigger_pipeline_end(total_batches=1, total_duration=0.1)
    manager.trigger_batch_start(batch_num=1, row_ids=[1])
    manager.trigger_batch_end(batch_num=1, duration=0.1)
    manager.trigger_loader_call(loader_name="l", params={}, result={"a": 1}, duration=0.01)
    manager.trigger_field_compute(field_key="f", row_id=1, dependencies={}, result=1)
    manager.trigger_error(error=RuntimeError("boom"), context={"x": 1})
    manager.trigger_diagnostic_warning(
        message="msg",
        source_id="s",
        field_id="f",
        lookup_key=1,
        row_id=1,
        sample_once=True,
    )
    manager.trigger_diagnostic_warning(
        message="msg",
        source_id="s",
        field_id="f",
        lookup_key=2,
        row_id=2,
        sample_once=True,
    )
    manager.trigger_field_slim(field_key="f", reason="x", batch_num=1, remaining_fields=0)
    manager.trigger_row_write(row_id=1, field_count=1, batch_num=1, row_index=0)
    manager.trigger_row_release(row_id=1, released_fields=[], retained_fields=[], batch_num=1)
    manager.trigger_loader_slim(loader_name="l", original_keys=2, extracted_fields=["a"], batch_num=1)
    manager.trigger_column_write(field_key="f", row_count=1, batch_num=1)

    seen_types = [t for t, _ in hook.events]
    assert EventType.DIAGNOSTIC_WARNING in seen_types


def test_hook_manager_trigger_diagnostic_warning_returns_when_not_subscribed() -> None:
    manager = HookManager()
    manager.register(BaseHook())
    manager.trigger_diagnostic_warning(message="msg", source_id="s", field_id="f", lookup_key=1, row_id=1)


def test_hook_manager_trigger_loader_call_and_loader_slim_return_when_unsubscribed() -> None:
    manager = HookManager()
    manager.register(_PartialTypedHook())  # type: ignore[arg-type]

    manager.trigger_pipeline_end(total_batches=0, total_duration=0.0)
    manager.trigger_batch_start(batch_num=1, row_ids=[1])
    manager.trigger_batch_end(batch_num=1, duration=0.0)
    manager.trigger_field_compute(field_key="f", row_id=1, dependencies={}, result=None)
    manager.trigger_error(RuntimeError("boom"), {})
    manager.trigger_field_slim(field_key="f", reason="x", batch_num=1, remaining_fields=0)
    manager.trigger_row_write(row_id=1, field_count=1, batch_num=1, row_index=0)
    manager.trigger_row_release(row_id=1, released_fields=[], retained_fields=[], batch_num=1)
    manager.trigger_loader_call(loader_name="l", params={}, result={"a": 1}, duration=0.01)
    manager.trigger_loader_slim(loader_name="l", original_keys=2, extracted_fields=["a"], batch_num=1)
    manager.trigger_column_write(field_key="f", row_count=1, batch_num=1)


def test_hook_manager_dispatch_strategy_is_replaceable() -> None:
    class _RecordingStrategy(HookDispatchStrategy):
        def __init__(self) -> None:
            self.dispatched = 0

        def dispatch(self, handler_pairs, event, safe_call):  # type: ignore[override,no-untyped-def]
            self.dispatched += len(handler_pairs)
            super(_RecordingStrategy, self).dispatch(handler_pairs, event, safe_call)

    strategy = _RecordingStrategy()
    hook = _PartialTypedHook()
    manager = HookManager(dispatch_strategy=strategy)
    manager.register(hook)  # type: ignore[arg-type]

    manager.trigger_pipeline_start(targets=["x"], batch_size=1)

    assert len(hook.pipeline_start_events) == 1
    assert strategy.dispatched == 1


def test_hook_manager_setstate_backfills_dispatch_strategy() -> None:
    manager = HookManager()
    state = manager.__getstate__()
    state["_dispatch_strategy"] = None

    restored = HookManager()
    restored.__setstate__(state)

    restored.register(_PartialTypedHook())  # type: ignore[arg-type]
    restored.trigger_pipeline_start(targets=["x"], batch_size=1)


def test_hook_manager_setstate_normalizes_hooks_collection() -> None:
    manager = HookManager()
    base_state = manager.__getstate__()

    tuple_state = dict(base_state)
    tuple_state["hooks"] = (_PartialTypedHook(),)
    tuple_state.pop("_has_hooks", None)
    restored_tuple = HookManager()
    restored_tuple.__setstate__(tuple_state)
    assert isinstance(restored_tuple.hooks, list)
    assert len(restored_tuple.hooks) == 1

    none_state = dict(base_state)
    none_state["hooks"] = None
    none_state.pop("_has_hooks", None)
    restored_none = HookManager()
    restored_none.__setstate__(none_state)
    assert restored_none.hooks == []
