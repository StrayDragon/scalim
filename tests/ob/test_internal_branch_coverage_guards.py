from collections import deque
import os
from typing import Any

import pytest

import threading

from scalim.events import Event
from scalim.events import EventType
from scalim.ob._internal.common import ObserverManagerMode
from scalim.ob.manager import ObserverManager
from scalim.ob._internal.manager_capture import ObserverManagerCaptureMixin
from scalim.ob._internal.manager_emit import ObserverManagerEmitMixin
from scalim.ob.presets._internal import viz_handlers as viz_handlers_module
from scalim.ob.presets._internal import viz_config as viz_config_module
from scalim.ob.presets._internal import viz_output as viz_output_module
from scalim.ob.observer import EventDispatchObserver, Observer
from scalim.ob.presets.viz import VizObserver


class _BrokenLen:
    def __len__(self) -> int:
        raise TypeError("no len")


class _NoopObserver(Observer):
    def on_event(self, event) -> None:  # type: ignore[override]
        _ = event


class _InvalidDispatchObserver(EventDispatchObserver):
    dispatch_map = {EventType.PIPELINE_START: 1}  # type: ignore[assignment]


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
            event_type=EventType.PIPELINE_START,
            timestamp=0.0,
            run_id="run",
            payload={},
            meta={},
            seq=1,
        )
    )
    emit_only.loader_result_policy = "SUMMARY"
    emit_only.emit_loader_call(loader_name="x", params={}, result={"a": 1}, duration=0.0)  # noqa: SLF001

    manager = ObserverManager(mode=ObserverManagerMode.CAPTURE)
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
    assert manager.wants(EventType.PIPELINE_START) is False

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


def test_internal_viz_nodes_cover_remaining_branch_arcs() -> None:
    observer = VizObserver(
        snapshot={
            "meta": {},
            "nodes": [
                {"type": "loader", "data": {}},
                {"id": "loader:orders", "type": "loader", "data": {}},
            ],
        }
    )
    assert observer._get_known_node_ids() == {"loader:orders"}  # noqa: SLF001
    assert observer._normalize_node_ref_id("loader:unknown extra") == "loader:unknown extra"  # noqa: SLF001

    observer_no_candidates = VizObserver(
        snapshot={
            "meta": {},
            "nodes": [{"id": "loader:orders", "type": "loader", "data": {}}],
        }
    )
    assert observer_no_candidates._normalize_node_ref_id("field:test") == "field:test"  # noqa: SLF001

    observer_candidates_no_value = VizObserver(
        snapshot={
            "meta": {},
            "nodes": [{"id": "field:test_a", "type": "field", "data": {}}],
        }
    )
    assert observer_candidates_no_value._normalize_node_ref_id("field:test") == "field:test_a"  # noqa: SLF001


def test_internal_viz_config_fill_paths_skip_branches(tmp_path) -> None:
    config = viz_config_module.VizObserverConfig(
        output_dir=str(tmp_path / "viz"),
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
        trace_path=str(tmp_path / "trace.jsonl"),
    )
    events_path, snapshot_path, trace_path = config._fill_paths_from_output_dir(  # noqa: SLF001
        str(tmp_path / "base"),
        config.output_path,
        config.snapshot_path,
        config.trace_path,
    )
    assert events_path == config.output_path
    assert snapshot_path == config.snapshot_path
    assert trace_path == config.trace_path


def test_internal_viz_output_emitters_cover_events_path_absent_branch(tmp_path) -> None:
    config = viz_config_module.VizObserverConfig(
        trace_path=str(tmp_path / "trace.jsonl"),
        trace_enabled=True,
    )
    observer = VizObserver(config=config)
    observer.run_id = "run"
    observer._ensure_emitters()  # noqa: SLF001
    assert observer._events_emitter is None  # noqa: SLF001
    assert observer._trace_emitter is not None  # noqa: SLF001
    observer.close()


def test_internal_viz_output_snapshot_cleanup_skips_when_temp_path_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    def _raise_oserror(_output_path: str, _suffix: str) -> str:
        raise OSError("boom")

    monkeypatch.setattr(viz_output_module, "create_temp_path", _raise_oserror)

    config = viz_config_module.VizObserverConfig(
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    observer = VizObserver(config=config, snapshot={"meta": {}, "nodes": []})
    observer._write_snapshot_if_needed()  # noqa: SLF001
