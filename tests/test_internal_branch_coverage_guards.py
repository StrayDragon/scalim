from collections import deque
import os
from typing import Any, List, Tuple

import pytest

import concurrent.futures
import threading

from scalim.execution.adaptive._internal.loadref_scheduler_support import run_task_in_process
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.events.event import Event
from scalim.execution.adaptive.policy import (
    ADAPTIVE_BACKEND_PROCESS,
    ADAPTIVE_BACKEND_THREAD,
    PROCESS_FAILURE_FAIL_FAST,
    PROCESS_FAILURE_FALLBACK_SERIAL,
    AdaptivePolicy,
)
from scalim.execution.adaptive.strategy_unit import TaskSpec
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob._internal.manager_capture import ObserverManagerCaptureMixin
from scalim.ob._internal.manager_emit import ObserverManagerEmitMixin
from scalim.planning.plan import ExecutionPlan
from scalim.execution.context import BatchContext
from scalim.events.catalog import EVENT_PIPELINE_START
from scalim.ob.presets._internal import viz_handlers as viz_handlers_module
from scalim.ob.presets._internal import viz_config as viz_config_module
from scalim.ob.observer import EventDispatchObserver, Observer
from scalim.ob.presets.viz import VizObserver


class _BrokenLen:
    def __len__(self) -> int:
        raise TypeError("no len")


class _NoopObserver(Observer):
    def on_event(self, event) -> None:  # type: ignore[override]
        _ = event


class _InvalidDispatchObserver(EventDispatchObserver):
    dispatch_map = {EVENT_PIPELINE_START: 1}  # type: ignore[assignment]


class _CaptureOnlyManager(ObserverManagerCaptureMixin):
    def __init__(self) -> None:
        self.debug_mode = False
        self.fallback_logger_enabled = False
        self.loader_result_policy = "full"
        self.loader_result_sample_size = 5
        self.run_id = "run"
        self.max_recorded_events = None
        self.capture_overflow_policy = "raise"
        self._lock = threading.RLock()
        self._supported_event_types = None
        self._observers_for_unknown_event_type = ()
        self._capture_event_types = None
        self._capture_unknown_event_types = False
        self._recorded_events = None


class _EmitOnlyManager(ObserverManagerEmitMixin):
    def __init__(self) -> None:
        self.observers = None
        self.debug_mode = False
        self.fallback_logger_enabled = False
        self.loader_result_policy = "full"
        self.run_id = "run"
        self.mode = "process"
        self._lock = threading.RLock()
        self._has_observers = False
        self._observers_by_event_type = None
        self._observers_for_unknown_event_type = ()
        self._diagnostic_warning_emitted = False
        self._seq = 0

    def _record_event(self, _event: Event) -> None:
        return None

    def _supports_safely(self, _observer: Observer, _event_type: str) -> bool:
        return True

    def _should_emit_event_type(self, _event_type: str) -> bool:
        return True

    def _summarize_result(self, _result: Any) -> dict:
        return {}

    def _sample_result(self, _result: Any) -> Any:
        return None


def test_internal_viz_handler_helpers_cover_guard_branches() -> None:
    assert viz_handlers_module._safe_len(_BrokenLen()) == 0
    assert viz_handlers_module._sample_value([1, 2, 3], 0) is None
    assert viz_handlers_module._sample_value(None, 2) is None

    sampled = viz_handlers_module._sample_value(set([1, 2, 3]), 1)
    assert isinstance(sampled, list)
    assert len(sampled) == 1

    marker = object()
    assert viz_handlers_module._sample_value(marker, 1) is marker


def test_internal_viz_output_default_dir_covers_platform_branches(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    assert viz_config_module.default_viz_dir().endswith(os.path.join("appdata", "scalim-viz"))

    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert "Application Support" in viz_config_module.default_viz_dir()


def test_internal_observer_manager_lazy_branches_and_viz_node_cache() -> None:
    capture_only = _CaptureOnlyManager()
    assert capture_only.drain_events() == []

    emit_only = _EmitOnlyManager()
    emit_only.close()
    emit_only._has_observers = True  # noqa: SLF001
    emit_only.emit(
        Event(
            event_type=EVENT_PIPELINE_START,
            timestamp=0.0,
            run_id="run",
            payload={},
            meta={},
            seq=1,
        )
    )

    manager = ObserverManager(mode="capture")
    manager._recorded_events = None  # noqa: SLF001
    assert manager.drain_events() == []

    manager._recorded_events = None  # noqa: SLF001
    manager.emit_pipeline_start(targets=["x"], batch_size=1)
    assert len(manager.drain_events()) == 1

    manager.observers = None
    manager.close()

    manager._has_observers = True  # noqa: SLF001
    manager._observers_by_event_type = None  # noqa: SLF001
    manager.emit_pipeline_start(targets=["x"], batch_size=1)

    manager = ObserverManager()
    manager.observers = None
    manager.register(_NoopObserver())
    manager._recorded_events = None  # noqa: SLF001
    manager.clear()

    manager._has_observers = True  # noqa: SLF001
    manager._supported_event_types = None  # noqa: SLF001
    assert manager.wants(EVENT_PIPELINE_START) is False

    assert manager._infer_eventdispatch_observer_event_types(_InvalidDispatchObserver()) == ()  # noqa: SLF001

    legacy = ObserverManager.__new__(ObserverManager)
    state = ObserverManager().__getstate__()
    state["_recorded_events"] = object()
    legacy.__setstate__(state)
    assert isinstance(legacy._recorded_events, deque)  # noqa: SLF001
    assert len(legacy._recorded_events) == 0  # noqa: SLF001

    viz_observer = VizObserver()
    viz_observer._node_id_cache = None  # noqa: SLF001
    assert viz_observer._normalize_node_ref_id("field:test") == "field:test"  # noqa: SLF001


class _RecordingPool:
    def __init__(self) -> None:
        self.calls = []

    def submit(self, fn, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        self.calls.append((fn, args, kwargs))
        fut = concurrent.futures.Future()
        fut.set_result("submitted")
        return fut


class _InvalidProcessFailurePolicy(AdaptivePolicy):
    def choose_process_failure_mode(self, *, plan, runtime, tuning):  # type: ignore[override]
        _ = plan
        _ = runtime
        _ = tuning
        return "invalid"


def test_adaptive_execution_internal_helpers_cover_process_paths() -> None:
    plan = ExecutionPlan()
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides(adaptive_policy=_InvalidProcessFailurePolicy()))
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)
    runtime.adaptive_process_failure_mode = PROCESS_FAILURE_FALLBACK_SERIAL

    assert scheduler._process_failure_mode(runtime) == PROCESS_FAILURE_FALLBACK_SERIAL  # noqa: SLF001
    runtime.adaptive_process_failure_mode = None
    assert scheduler._process_failure_mode(runtime) == PROCESS_FAILURE_FAIL_FAST  # noqa: SLF001
    assert scheduler._should_use_process_backend(ADAPTIVE_BACKEND_PROCESS) is True  # noqa: SLF001
    assert scheduler._should_use_process_backend(ADAPTIVE_BACKEND_THREAD) is False  # noqa: SLF001

    pool = _RecordingPool()
    context = BatchContext()
    spec = TaskSpec(op=object(), relation_key=(("k",),), group_enabled=True, pool_name="default")
    future = scheduler._submit_process_task(  # noqa: SLF001
        spec,
        pool=pool,
        context=context,
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
    )

    assert future.result() == "submitted"
    assert len(pool.calls) == 1
    fn, args, kwargs = pool.calls[0]
    assert fn is run_task_in_process
    assert args[0] is plan
    assert args[3] is not context
    assert args[4] == [0]
    assert kwargs == {"group_enabled": True}
