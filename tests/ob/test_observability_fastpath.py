from scalim.events import EVENT_PIPELINE_END, EVENT_PIPELINE_START
from scalim.hooks import BaseHook, HookManager
from scalim.ob.observer import Observer
from scalim.ob.manager import ObserverManager


class _ExplodingSampleHookManager(HookManager):
    def _sample_result(self, result):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected _sample_result call")

    def _summarize_result(self, result):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected _summarize_result call")


class _ExplodingSampleObserverManager(ObserverManager):
    def _sample_result(self, result):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected _sample_result call")

    def _summarize_result(self, result):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected _summarize_result call")


class _CaptureObserver(Observer):
    event_types = {EVENT_PIPELINE_START}

    def __init__(self) -> None:
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_hook_manager_fastpath_skips_loader_sampling_when_no_hooks() -> None:
    manager = _ExplodingSampleHookManager(loader_result_policy="sample", loader_result_sample_size=1)
    manager.trigger_loader_call("loader", {}, [1, 2, 3], 0.1)


def test_observer_manager_fastpath_skips_loader_sampling_when_no_observers() -> None:
    manager = _ExplodingSampleObserverManager(loader_result_policy="sample", loader_result_sample_size=1)
    manager.emit_loader_call("loader", {}, [1, 2, 3], 0.1)


def test_observer_manager_subscription_cache_gates_typed_emits() -> None:
    observer = _CaptureObserver()
    manager = ObserverManager()
    manager.register(observer)

    manager.emit_pipeline_start(targets=["x"], batch_size=1)
    manager.emit_pipeline_end(total_batches=0, total_duration=0.0)

    assert len(observer.events) == 1
    assert observer.events[0].event_type == EVENT_PIPELINE_START

    assert manager.unregister(observer) is True
    manager.emit_pipeline_start(targets=["x"], batch_size=1)
    assert len(observer.events) == 1


def test_observer_manager_capture_mode_still_records_typed_events() -> None:
    manager = ObserverManager(mode="capture")
    manager.emit_pipeline_start(targets=["x"], batch_size=1)
    events = manager.drain_events()
    assert len(events) == 1
    assert events[0].event_type == EVENT_PIPELINE_START

    manager.emit_event(EVENT_PIPELINE_END, {"x": 1})
    assert len(manager.drain_events()) == 1


def test_hook_manager_setstate_backfills_has_hooks_for_legacy_pickles() -> None:
    state = HookManager().__getstate__()
    state.pop("_has_hooks", None)
    state["hooks"] = [BaseHook()]

    legacy = HookManager.__new__(HookManager)
    legacy.__setstate__(state)
    assert legacy._has_hooks is True  # noqa: SLF001


def test_hook_manager_fastpath_resets_stale_has_hooks_when_empty() -> None:
    manager = HookManager()

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_pipeline_start(targets=["x"], batch_size=1)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_pipeline_end(total_batches=0, total_duration=0.0)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_batch_start(batch_num=1, row_ids=[1])
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_batch_end(batch_num=1, duration=0.0)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_loader_call("loader", {}, [1, 2, 3], 0.1)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_field_compute("f", 1, {}, 1)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_error(RuntimeError("boom"), {})
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_field_slim("f", "reason", batch_num=1, remaining_fields=0)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_row_write(row_id=1, field_count=1, batch_num=1, row_index=0)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_row_release(row_id=1, released_fields=[], retained_fields=[], batch_num=1)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_loader_slim(loader_name="loader", original_keys=1, extracted_fields=[], batch_num=1)
    assert manager._has_hooks is False  # noqa: SLF001

    manager._has_hooks = True  # noqa: SLF001
    manager.trigger_column_write(field_key="f", row_count=1, batch_num=1)
    assert manager._has_hooks is False  # noqa: SLF001


def test_hook_manager_trigger_error_returns_when_no_hooks() -> None:
    manager = HookManager()
    manager.trigger_error(RuntimeError("boom"), {})


def test_observer_manager_setstate_backfills_subscription_cache_for_legacy_pickles() -> None:
    state = ObserverManager().__getstate__()
    state.pop("_has_observers", None)
    state.pop("_supports_all", None)
    state.pop("_supported_event_types", None)
    state.pop("_capture_event_types", None)

    legacy = ObserverManager.__new__(ObserverManager)
    legacy.__setstate__(state)
    assert legacy._has_observers is False  # noqa: SLF001


class _SupportsNeverObserver(Observer):
    def supports(self, event_type: str) -> bool:
        _ = event_type
        return False

    def __init__(self) -> None:
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_observer_manager_emit_skips_when_custom_supports_returns_false() -> None:
    observer = _SupportsNeverObserver()
    manager = ObserverManager(observers=[observer])

    manager.emit_event(EVENT_PIPELINE_START, {"x": 1})
    assert observer.events == []


class _AllEventsObserver(Observer):
    def __init__(self) -> None:
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_observer_manager_emit_error_emits_when_observer_present() -> None:
    observer = _AllEventsObserver()
    manager = ObserverManager(observers=[observer])
    manager.emit_error(RuntimeError("boom"), {"x": 1})
    assert observer.events
