# region imports

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scalim.events import EventType
from scalim.events import Event
from scalim.events._events import (
    AdaptiveSchedulerDecisionEvent,
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    OutputTargetEndEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from scalim.execution.output_composition import AuditSheetSpec, MetaSheetSpec, OutputCompositionSpec, OutputTargetSpec
from scalim.execution.output_contracts import ExportLayout, OutputSpec
from scalim.ob.presets._internal import viz_config as viz_config_module
from scalim.ob.presets._internal import viz_handlers as viz_handlers_module
from scalim.ob.presets.viz import VizEventEmitter, VizObserver, VizObserverConfig
from tests.support.testing_utils import CI_TIMEOUT_S
from tests.support.event_envelope import event_envelope

# endregion


class DummyLogger:
    def __init__(self) -> None:
        self.messages = []

    def warning(self, msg: str, *args: Any) -> None:
        self.messages.append(msg % args)


class BrokenLen:
    def __len__(self) -> int:
        raise AttributeError("no len")


class BrokenHandle:
    def write(self, _: str) -> None:
        raise OSError("write failed")

    def flush(self) -> None:
        raise OSError("flush failed")

    def close(self) -> None:
        return None


class BrokenCloseHandle:
    def close(self) -> None:
        raise OSError("close failed")


def test_viz_helpers_and_config_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    win_dir = viz_config_module.default_viz_dir()
    assert win_dir.endswith(os.path.join("appdata", "scalim-viz"))

    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    darwin_dir = viz_config_module.default_viz_dir()
    assert "Application Support" in darwin_dir
    assert darwin_dir.endswith(os.path.join("Application Support", "scalim-viz"))

    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    linux_dir = viz_config_module.default_viz_dir()
    assert linux_dir.endswith(os.path.join("xdg", "scalim-viz"))

    assert viz_config_module.normalize_output_dir(str(tmp_path / "run-root")).endswith("scalim-viz")
    assert viz_config_module.normalize_output_dir(str(tmp_path / "scalim-viz")) == os.path.normpath(str(tmp_path / "scalim-viz"))
    assert viz_config_module.normalize_output_dir(str(tmp_path / "scalim-viz" / "run1")) == os.path.normpath(
        str(tmp_path / "scalim-viz" / "run1")
    )

    assert viz_handlers_module._safe_len([1, 2]) == 2
    assert viz_handlers_module._safe_len(5) == 0
    assert viz_handlers_module._safe_len(BrokenLen()) == 0

    assert viz_handlers_module._sample_value(None, 1) is None
    assert viz_handlers_module._sample_value([1, 2, 3], 2) == [1, 2]
    assert viz_handlers_module._sample_value((1, 2, 3), 2) == [1, 2]
    assert viz_handlers_module._sample_value({"a": 1, "b": 2}, 1) == {"a": 1}
    assert viz_handlers_module._sample_value({"a": {"b": 1}}, 1) == {"a": {"b": 1}}
    assert viz_handlers_module._sample_value(set([1, 2, 3]), 1)
    assert viz_handlers_module._sample_value("abc", 2) == "abc"
    assert viz_handlers_module._sample_value([1, 2, 3], 0) is None

    local = VizObserverConfig.default_local()
    assert local.output_dir

    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "default"))
    config = VizObserverConfig(use_default_output_dir=True)
    events_path, snapshot_path, trace_path = config.resolve_output_paths()
    assert events_path.endswith(os.path.join("scalim-viz", "viz_events.jsonl"))
    assert snapshot_path.endswith(os.path.join("scalim-viz", "viz_snapshot.json"))
    assert trace_path.endswith(os.path.join("scalim-viz", "viz_trace.jsonl"))

    monkeypatch.setenv("HOME", str(tmp_path))
    config = VizObserverConfig(output_path="~/events.jsonl", snapshot_path="~/snapshot.json")
    events_path, snapshot_path, trace_path = config.resolve_output_paths()
    assert str(tmp_path) in events_path
    assert str(tmp_path) in snapshot_path
    assert trace_path.endswith(os.path.join(str(tmp_path), "viz_trace.jsonl"))

    config = VizObserverConfig(output_dir=str(tmp_path / "runs"), events_filename="evt.jsonl", snapshot_filename="snap.json")
    events_path, snapshot_path, trace_path = config.resolve_output_paths()
    assert events_path.endswith(os.path.join("scalim-viz", "evt.jsonl"))
    assert snapshot_path.endswith(os.path.join("scalim-viz", "snap.json"))
    assert trace_path.endswith(os.path.join("scalim-viz", "viz_trace.jsonl"))


def test_viz_event_emitter_success_and_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = DummyLogger()
    out_path = tmp_path / "events" / "viz_events.jsonl"
    config = VizObserverConfig(output_path=str(out_path), logger=logger)

    emitter = VizEventEmitter(None)
    assert emitter._output_handle is None

    emitter = VizEventEmitter(config.output_path, logger=config.logger)
    emitter.emit({"ok": True})
    emitter.close()
    text = out_path.read_text(encoding="utf-8").strip()
    assert '"ok": true' in text
    assert emitter._output_handle is None

    emitter = VizEventEmitter(config.output_path, logger=config.logger)
    original_handle = emitter._output_handle
    emitter._output_handle = BrokenHandle()
    emitter.emit({"ok": True})
    emitter.close(timeout=CI_TIMEOUT_S)
    if original_handle is not None:
        original_handle.close()
    assert logger.messages

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("fail open")

    monkeypatch.setattr(Path, "open", boom)
    emitter = VizEventEmitter(config.output_path, logger=config.logger)
    assert emitter._output_handle is None


def test_viz_event_emitter_additional_branches(tmp_path: Path) -> None:
    import queue
    import threading

    logger = DummyLogger()

    # Cover: close(timeout=0) warning branch.
    timeout_path = tmp_path / "timeout.jsonl"
    emitter = VizEventEmitter(str(timeout_path), logger=logger)
    writer = emitter._writer_thread
    emitter.close(timeout=0.0)
    if writer is not None:
        writer.join(timeout=CI_TIMEOUT_S)
        assert not writer.is_alive()
    assert any("关闭事件写线程超时" in msg for msg in logger.messages)

    # Cover: close() when output_handle.close raises OSError.
    close_path = tmp_path / "broken_close.jsonl"
    emitter = VizEventEmitter(str(close_path), logger=logger)
    original_handle = emitter._output_handle
    emitter._output_handle = BrokenCloseHandle()
    emitter.close()
    if original_handle is not None:
        original_handle.close()
    assert any("关闭事件输出失败" in msg for msg in logger.messages)

    # Cover: _writer_main early return when queue is missing.
    disabled = VizEventEmitter(None, logger=logger)
    disabled._writer_main()
    disabled.close()

    # Cover: emit() returns early when closing is set.
    closing_path = tmp_path / "closing.jsonl"
    emitter = VizEventEmitter(str(closing_path), logger=logger)
    emitter._closing.set()
    emitter.emit({"ok": True})
    emitter.close()

    # Cover: writer handles missing output handle gracefully.
    missing_handle_path = tmp_path / "missing_handle.jsonl"
    emitter = VizEventEmitter(str(missing_handle_path), logger=logger)
    original_handle = emitter._output_handle
    emitter._output_handle = None
    emitter.emit({"ok": True})
    emitter.close()
    if original_handle is not None:
        original_handle.close()

    # Cover: emit() handles unexpected put errors.
    class BrokenQueue:
        def put(self, *_args: Any, **_kwargs: Any) -> None:
            raise ValueError("boom")

    emitter = VizEventEmitter(None, logger=logger)
    emitter._queue = BrokenQueue()  # type: ignore[assignment]
    emitter.emit({"ok": True})
    emitter.close()
    assert any("写入事件失败" in msg for msg in logger.messages)

    # Cover: queue.Full + closing short-circuit in emit loop.
    class AlwaysFullQueue:
        def __init__(self) -> None:
            self.put_called = threading.Event()

        def put(self, *_args: Any, **_kwargs: Any) -> None:
            self.put_called.set()
            raise queue.Full()

    emitter = VizEventEmitter(None, logger=logger)
    full_queue = AlwaysFullQueue()
    emitter._queue = full_queue  # type: ignore[assignment]

    emit_thread = threading.Thread(target=emitter.emit, args=({"ok": True},))
    emit_thread.start()
    assert full_queue.put_called.wait(timeout=CI_TIMEOUT_S)
    emitter.close()
    emit_thread.join(timeout=CI_TIMEOUT_S)
    assert not emit_thread.is_alive()


def test_viz_event_emitter_concurrent_emission_keeps_jsonl_valid(tmp_path: Path) -> None:
    import threading

    events_path = tmp_path / "viz_events.jsonl"
    trace_path = tmp_path / "viz_trace.jsonl"
    events_emitter = VizEventEmitter(str(events_path))
    trace_emitter = VizEventEmitter(str(trace_path))
    threads = []
    started = threading.Barrier(parties=8)

    def _worker(tid: int) -> None:
        started.wait()
        for idx in range(50):
            events_emitter.emit({"t": int(tid), "i": int(idx)})
            trace_emitter.emit({"t": int(tid), "i": int(idx)})

    for tid in range(8):
        threads.append(threading.Thread(target=_worker, args=(tid,)))
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=CI_TIMEOUT_S)
        assert not t.is_alive()
    events_emitter.close(timeout=CI_TIMEOUT_S)
    trace_emitter.close(timeout=CI_TIMEOUT_S)

    events_lines = events_path.read_text(encoding="utf-8").splitlines()
    trace_lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(events_lines) == 400
    assert len(trace_lines) == 400
    for line in events_lines:
        _ = json.loads(line)
    for line in trace_lines:
        _ = json.loads(line)


def test_viz_snapshot_concurrent_writers_keep_json_parseable(tmp_path: Path) -> None:
    import threading

    snapshot_path = tmp_path / "viz_snapshot.json"
    errors = []
    stop = threading.Event()
    started = threading.Barrier(parties=5)

    def _writer(tid: int) -> None:
        started.wait(timeout=CI_TIMEOUT_S)
        for idx in range(10):
            observer = VizObserver(
                config=VizObserverConfig(snapshot_path=str(snapshot_path)),
                snapshot={
                    "meta": {"t": int(tid), "i": int(idx)},
                    "nodes": [
                        {"id": f"n:{j}", "type": "node", "data": {"label": "x" * 200}, "position": {"x": j, "y": j}} for j in range(25)
                    ],
                    "edges": [],
                },
            )
            observer._write_snapshot_if_needed()

    def _reader() -> None:
        started.wait(timeout=CI_TIMEOUT_S)
        while not stop.is_set():
            if not snapshot_path.exists():
                stop.wait(timeout=0.001)
                continue
            try:
                _ = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
                return
            stop.wait(timeout=0.001)

    reader = threading.Thread(target=_reader)
    writers = [threading.Thread(target=_writer, args=(tid,)) for tid in range(4)]

    reader.start()
    for t in writers:
        t.start()

    for t in writers:
        t.join(timeout=CI_TIMEOUT_S)
        assert not t.is_alive()

    stop.set()
    reader.join(timeout=CI_TIMEOUT_S)
    assert not reader.is_alive()

    if errors:
        raise AssertionError(errors)
    _ = json.loads(snapshot_path.read_text(encoding="utf-8"))


def test_viz_event_emitter_handles_serialization_error_and_disabled_output() -> None:
    logger = DummyLogger()
    emitter = VizEventEmitter(None, logger=logger)
    emitter.emit({"ok": True})

    circular: Any = {}
    circular["self"] = circular
    emitter.emit(circular)
    assert logger.messages


def test_viz_observer_hook_emits_events(tmp_path: Path) -> None:
    output_path = tmp_path / "viz_events.jsonl"
    snapshot_path = tmp_path / "viz_snapshot.json"
    trace_path = tmp_path / "viz_trace.jsonl"
    snapshot = {"meta": "invalid"}
    config = VizObserverConfig(
        output_path=str(output_path),
        snapshot_path=str(snapshot_path),
        trace_enabled=True,
        payload_policy="sample",
        sample_size=1,
        run_name="demo",
        env="dev",
    )
    hook = VizObserver(config=config, snapshot=snapshot)

    hook.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=10)))
    hook.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1, 2, 3])))
    hook.on_loader_call(
        event_envelope(
            LoaderCallEvent(
                loader_name="orders",
                params={},
                result={"order": {"order_id": 1}, "status": "ok"},
                duration=0.01,
                batch_num=1,
                cache_status="miss",
                lookup_key_count=2,
                field_keys=["order_id"],
            )
        )
    )
    hook.on_field_compute(event_envelope(FieldComputeEvent(field_key="profit", row_id=1, dependencies={"a": 1}, result=10)))
    hook.on_error(event_envelope(ErrorEvent(ValueError("boom"), {"field_key": "profit", "row_id": 1})))
    hook.on_diagnostic_warning(
        event_envelope(
            DiagnosticWarningEvent(
                message="float lookup key",
                source_id="orders",
                field_id="profit",
                lookup_key="1001.0",
                row_id=1,
            )
        )
    )
    hook.on_column_write(event_envelope(ColumnWriteEvent(field_key="profit", row_count=2, batch_num=1)))
    hook.on_row_write(event_envelope(RowWriteEvent(row_id=1, field_count=2, batch_num=1, row_index=0)))
    hook.on_row_release(event_envelope(RowReleaseEvent(row_id=1, released_fields=["a"], retained_fields=["b"], batch_num=1)))
    hook.on_field_slim(event_envelope(FieldSlimEvent(field_key="profit", reason="done", batch_num=1, remaining_fields=0)))
    hook.on_loader_slim(event_envelope(LoaderSlimEvent(loader_name="orders", original_keys=2, extracted_fields=["order_id"], batch_num=1)))
    hook.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.02)))
    hook.on_event(
        Event(
            event_type=EventType.OUTPUT_TARGET_END,
            timestamp=0.0,
            run_id="run_test",
            payload=OutputTargetEndEvent(
                target_id="summary",
                output_path="/tmp/demo.xlsx",
                sheet_name="Summary",
                row_count=10,
                error_count=1,
                duration=1.2,
                disabled=False,
                error_type="ValueError",
                error_message="boom",
            ),
        )
    )
    hook.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.3)))

    assert snapshot_path.exists()
    assert output_path.exists()
    assert trace_path.exists()

    events = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = {evt["event_type"] for evt in events}
    assert {"run_started", "run_finished", "error", "diagnostic_warning"} <= event_types
    assert "output_target_finished" in event_types
    assert "row_written" not in event_types
    assert "field_computed" not in event_types

    output_events = [evt for evt in events if evt.get("event_type") == "output_target_finished"]
    assert output_events
    output_event = output_events[-1]
    assert output_event["node_ref"]["type"] == "output_target"
    assert output_event["node_ref"]["id"] == "output_target:summary"
    payload = output_event.get("payload") or {}
    assert payload.get("target_id") == "summary"
    assert payload.get("row_count") == 10
    assert payload.get("error_count") == 1
    assert payload.get("duration_ms") == 1200
    assert payload.get("output_path") == "/tmp/demo.xlsx"
    assert payload.get("sheet_name") == "Summary"
    assert payload.get("error_type") == "ValueError"
    assert payload.get("error_message") == "boom"

    trace_events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    trace_event_types = {evt["event_type"] for evt in trace_events}
    assert {"row_written", "row_released", "field_computed"} <= trace_event_types


def test_viz_output_target_end_handler_branches(tmp_path: Path) -> None:
    disabled = VizObserver(config=VizObserverConfig())
    disabled.on_output_target_end(
        event_envelope(
            OutputTargetEndEvent(
                target_id="t1",
                output_path="/tmp/demo.xlsx",
                sheet_name="Sheet1",
                row_count=0,
                error_count=0,
                duration=0.0,
                disabled=False,
                error_type=None,
                error_message=None,
            )
        )
    )

    output_path = tmp_path / "events.jsonl"
    enabled = VizObserver(config=VizObserverConfig(output_path=str(output_path)), snapshot={"meta": {}})
    enabled.on_output_target_end(
        event_envelope(
            OutputTargetEndEvent(
                target_id="t1",
                output_path="/tmp/demo.xlsx",
                sheet_name="Sheet1",
                row_count=0,
                error_count=0,
                duration=0.0,
                disabled=False,
                error_type=None,
                error_message=None,
            )
        )
    )
    assert not output_path.exists()


def test_viz_observer_hook_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = VizObserver()

    class DummyPlan:
        def to_viz_graph_snapshot(self) -> dict:
            return {"meta": {}, "nodes": [], "edges": []}

    _ = VizObserver.from_plan(DummyPlan(), VizObserverConfig(output_path=str(tmp_path / "plan.jsonl")))

    disabled = VizObserver(config=VizObserverConfig())
    disabled.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    disabled.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))
    disabled.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1])))
    disabled.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.1)))
    disabled.on_loader_call(event_envelope(LoaderCallEvent(loader_name="orders", params={}, result=[], duration=0.0)))
    disabled.on_field_compute(event_envelope(FieldComputeEvent(field_key="profit", row_id=1, dependencies={}, result=None)))
    disabled.on_error(event_envelope(ErrorEvent(ValueError("boom"), {"field_key": "profit"})))
    disabled.on_diagnostic_warning(
        event_envelope(DiagnosticWarningEvent(message="warn", source_id="orders", field_id="profit", lookup_key="k", row_id=1))
    )
    disabled.on_column_write(event_envelope(ColumnWriteEvent(field_key="profit", row_count=1, batch_num=1)))
    disabled.on_row_write(event_envelope(RowWriteEvent(row_id=1, field_count=1, batch_num=1, row_index=0)))
    disabled.on_row_release(event_envelope(RowReleaseEvent(row_id=1, released_fields=[], retained_fields=[], batch_num=1)))
    disabled.on_field_slim(event_envelope(FieldSlimEvent(field_key="profit", reason="done", batch_num=1, remaining_fields=0)))
    disabled.on_loader_slim(event_envelope(LoaderSlimEvent(loader_name="orders", original_keys=0, extracted_fields=[], batch_num=1)))

    config = VizObserverConfig(output_dir=str(tmp_path))
    hook = VizObserver(config=config, snapshot={"meta": {}})
    hook.run_id = "run_1"
    hook.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    assert hook.config.output_dir is not None
    assert hook.config.output_dir.endswith(os.path.join("scalim-viz", "run_1"))
    events_path = Path(hook.config.output_dir) / "viz_events.jsonl"
    snapshot_path = Path(hook.config.output_dir) / "viz_snapshot.json"
    assert events_path.exists()
    assert snapshot_path.exists()

    hook = VizObserver(config=VizObserverConfig(output_dir=None, use_default_output_dir=False))
    hook.run_id = "run_2"
    hook._apply_run_output_dir()
    assert hook.config.output_dir is None

    monkeypatch.setattr(viz_config_module.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "default"))
    hook = VizObserver(config=VizObserverConfig(output_dir=None, use_default_output_dir=True))
    hook.run_id = "run_3"
    hook._apply_run_output_dir()
    assert hook.config.output_dir is not None
    assert hook.config.output_dir.endswith(os.path.join("scalim-viz", "run_3"))

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events_path.jsonl")))
    hook.run_id = "run_4"
    hook._apply_run_output_dir()
    assert hook.config.output_dir is None

    config = VizObserverConfig(output_path=str(tmp_path / "events.jsonl"))
    hook = VizObserver(config=config, snapshot={"meta": {}})
    hook.run_id = "run_5"
    hook._ensure_emitters()
    assert hook._events_emitter is not None
    assert hook._trace_emitter is None
    hook.close()

    config = VizObserverConfig(output_path=str(tmp_path / "events_trace.jsonl"), trace_enabled=True)
    hook = VizObserver(config=config, snapshot={"meta": {}})
    hook.run_id = "run_6"
    hook._ensure_emitters()
    assert hook._events_emitter is not None
    assert hook._trace_emitter is not None
    hook.close()

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("fail write")

    monkeypatch.setattr(Path, "open", boom)
    hook = VizObserver(
        config=VizObserverConfig(output_path=str(tmp_path / "events5.jsonl"), snapshot_path=str(tmp_path / "snap.json")),
        snapshot={"meta": {}},
    )
    hook._write_snapshot_if_needed()


def test_viz_observer_from_plan_augments_output_targets(tmp_path: Path) -> None:
    class DummyPlan:
        def to_viz_graph_snapshot(self) -> dict:
            return {
                "meta": {},
                "nodes": [
                    {"id": "field:order_id", "type": "field", "data": {"label": "order_id"}, "position": {"x": 0, "y": 0}},
                    {"id": "field:profit", "type": "field", "data": {"label": "profit"}, "position": {"x": 0, "y": 0}},
                ],
                "edges": [],
                "stages": [],
            }

    output_composition = OutputCompositionSpec(
        targets=(
            OutputTargetSpec(
                target_id="main",
                layout=ExportLayout(field_ids=("order_id", "profit")),
                output=OutputSpec(format="csv", path=str(tmp_path / "out.csv")),
                predicate=None,
                is_primary=True,
                requires=None,
            ),
        ),
        derived_targets=(),
        meta_sheet=None,
        audit_sheet=None,
        failure_policy="all_fail",
        include_full_error_message=False,
    )

    observer = VizObserver.from_plan(DummyPlan(), VizObserverConfig(), output_composition=output_composition)
    snapshot = observer.snapshot
    assert snapshot is not None
    nodes = snapshot.get("nodes") or []
    edges = snapshot.get("edges") or []

    output_nodes = [n for n in nodes if n.get("type") == "output_target"]
    assert any(n.get("id") == "output_target:main" for n in output_nodes)

    edge_types = {(e.get("source"), e.get("target"), e.get("type")) for e in edges}
    assert ("field:order_id", "output_target:main", "composed_from") in edge_types
    assert ("field:profit", "output_target:main", "composed_from") in edge_types


def test_viz_output_composition_snapshot_helpers_cover_branches() -> None:
    import scalim.ob.presets.viz.output_composition as viz_module

    assert viz_module._get_snapshot_node_ids({"nodes": {"id": "nope"}}) == set()
    assert viz_module._get_snapshot_node_ids({"nodes": [{"id": "a"}, {"id": 1}, {}]}) == {"a", "1"}

    snapshot = {"nodes": [{"id": "x"}]}
    assert viz_module._ensure_snapshot_list(snapshot, "nodes") is snapshot["nodes"]

    snapshot2: dict = {"edges": "nope"}
    edges = viz_module._ensure_snapshot_list(snapshot2, "edges")
    assert edges == []
    assert snapshot2["edges"] is edges

    edge_keys = viz_module._get_snapshot_edge_keys(
        [
            {"source": "a", "target": "b", "type": "t"},
            {"source": "", "target": "b", "type": "t"},
            {"source": "a", "target": "", "type": "t"},
            {"source": "a", "target": "b", "type": ""},
        ]
    )
    assert edge_keys == {("a", "b", "t")}

    assert viz_module._as_optional_text(None) is None
    assert viz_module._as_optional_text("") is None
    assert viz_module._as_optional_text(123) == "123"

    assert viz_module._describe_output_spec(None) == (None, None)
    assert viz_module._describe_output_spec(SimpleNamespace(path="/tmp/out", sheet_name="")) == ("/tmp/out", None)

    nodes: list = []
    node_ids = set()
    viz_module._add_output_target_node(
        nodes,
        node_ids,
        target_id="t1",
        kind="direct",
        output_path="/tmp/out",
        sheet_name=None,
        is_primary=True,
    )
    viz_module._add_output_target_node(
        nodes,
        node_ids,
        target_id="t1",
        kind="direct",
        output_path="/tmp/out",
        sheet_name=None,
        is_primary=True,
    )
    assert [n.get("id") for n in nodes] == ["output_target:t1"]

    assert viz_module._iter_unique_field_ids(["a", "", "a"], requires=("b", "a")) == ("a", "b")

    edges = []
    edge_keys_set = set()
    node_ids_edges = set(["field:a"])
    viz_module._maybe_add_output_target_edge(edges, edge_keys_set, node_ids_edges, source_field_id="a", target_id="t1")
    assert edges == []

    node_ids_edges.add("output_target:t1")
    viz_module._maybe_add_output_target_edge(edges, edge_keys_set, node_ids_edges, source_field_id="a", target_id="t1")
    viz_module._maybe_add_output_target_edge(edges, edge_keys_set, node_ids_edges, source_field_id="a", target_id="t1")
    assert len(edges) == 1

    nodes = []
    node_ids = set()
    viz_module._append_output_target_nodes_for_targets(
        nodes,
        node_ids,
        targets=[
            SimpleNamespace(target_id=None),
            SimpleNamespace(target_id="t2", output=None, is_primary=False),
        ],
        kind="direct",
    )
    assert any(n.get("id") == "output_target:t2" for n in nodes)

    nodes = []
    node_ids = set()
    viz_module._append_output_target_node_for_sheet(nodes, node_ids, sheet=SimpleNamespace(target_id=None), kind="meta_sheet")
    assert nodes == []
    viz_module._append_output_target_node_for_sheet(
        nodes,
        node_ids,
        sheet=SimpleNamespace(
            target_id="meta",
            output=OutputSpec(format="excel", path="/tmp/out.xlsx", sheet_name="FromOutput"),
            sheet_name="",
        ),
        kind="meta_sheet",
    )
    meta_node = [n for n in nodes if n.get("id") == "output_target:meta"][0]
    assert meta_node.get("data", {}).get("sheet_name") == "FromOutput"

    edges = []
    edge_keys_set = set()
    node_ids = set(["field:a", "field:b", "output_target:t3"])
    viz_module._append_output_target_edges_for_direct_targets(
        edges,
        edge_keys_set,
        node_ids,
        targets=[
            SimpleNamespace(target_id=None),
            SimpleNamespace(target_id="t_skip_layout", layout=None, requires=None),
            SimpleNamespace(target_id="t_skip_field_ids", layout=SimpleNamespace(), requires=None),
            SimpleNamespace(target_id="t3", layout=ExportLayout(field_ids=("a",)), requires=("b",)),
        ],
    )
    assert {(e.get("source"), e.get("target")) for e in edges} == {("field:a", "output_target:t3"), ("field:b", "output_target:t3")}

    class DummyDerived:
        def __init__(self, fields):
            self._fields = fields

        def required_fields(self):
            return self._fields

    edges = []
    edge_keys_set = set()
    node_ids = set(["field:x", "field:y", "field:z", "output_target:d_ok"])
    viz_module._append_output_target_edges_for_derived_targets(
        edges,
        edge_keys_set,
        node_ids,
        targets=[
            SimpleNamespace(target_id=None),
            SimpleNamespace(target_id="d_none", derived=None, requires=None),
            SimpleNamespace(target_id="d_no_method", derived=SimpleNamespace(), requires=None),
            SimpleNamespace(target_id="d_not_callable", derived=SimpleNamespace(required_fields="nope"), requires=None),
            SimpleNamespace(target_id="d_ok", derived=DummyDerived(["x", "y"]), requires=("z",)),
        ],
    )
    assert {(e.get("source"), e.get("target")) for e in edges} == {
        ("field:x", "output_target:d_ok"),
        ("field:y", "output_target:d_ok"),
        ("field:z", "output_target:d_ok"),
    }

    assert (
        viz_module.augment_viz_graph_snapshot_for_output_composition(
            {},
            output_composition=SimpleNamespace(targets=(), derived_targets=(), meta_sheet=None, audit_sheet=None),
        )
        == {}
    )

    snapshot = {"meta": {}, "nodes": [{"id": "field:a", "type": "field", "data": {}, "position": {"x": 0, "y": 0}}], "edges": []}
    output_composition = OutputCompositionSpec(
        targets=(),
        derived_targets=(),
        meta_sheet=MetaSheetSpec(
            target_id="meta",
            output=OutputSpec(format="excel", path="/tmp/out.xlsx", sheet_name="meta-from-output"),
            sheet_name="__meta__",
        ),
        audit_sheet=AuditSheetSpec(
            target_id="audit",
            output=OutputSpec(format="excel", path="/tmp/out.xlsx", sheet_name="audit-from-output"),
            sheet_name="__audit__",
        ),
        failure_policy="all_fail",
        include_full_error_message=False,
    )
    snapshot = viz_module.augment_viz_graph_snapshot_for_output_composition(snapshot, output_composition=output_composition)
    nodes = snapshot.get("nodes") or []
    assert any(n.get("id") == "output_target:meta" for n in nodes)
    assert any(n.get("id") == "output_target:audit" for n in nodes)


def test_viz_output_path_truncates_by_default_and_append_is_opt_in(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    snapshot_path = tmp_path / "snapshot.json"

    config = VizObserverConfig(output_path=str(events_path), snapshot_path=str(snapshot_path))
    observer = VizObserver(config=config, snapshot={"meta": {}})
    observer.run_id = "run_a"
    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))
    text = events_path.read_text(encoding="utf-8")
    assert "run_a" in text

    observer2 = VizObserver(config=config, snapshot={"meta": {}})
    observer2.run_id = "run_b"
    observer2.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer2.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))
    text = events_path.read_text(encoding="utf-8")
    assert "run_b" in text
    assert "run_a" not in text

    events_path_append = tmp_path / "events_append.jsonl"
    snapshot_path_append = tmp_path / "snapshot_append.json"
    config_append = VizObserverConfig(output_path=str(events_path_append), snapshot_path=str(snapshot_path_append), append=True)
    observer3 = VizObserver(config=config_append, snapshot={"meta": {}})
    observer3.run_id = "run_c"
    observer3.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer3.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))
    observer4 = VizObserver(config=config_append, snapshot={"meta": {}})
    observer4.run_id = "run_d"
    observer4.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer4.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))
    text = events_path_append.read_text(encoding="utf-8")
    assert "run_c" in text
    assert "run_d" in text


def test_viz_node_ref_normalization_and_loader_display_name(tmp_path: Path) -> None:
    events_path = tmp_path / "viz_events.jsonl"
    trace_path = tmp_path / "viz_trace.jsonl"
    snapshot_path = tmp_path / "viz_snapshot.json"

    snapshot = {
        "meta": {"target_fields": ["profit"]},
        "nodes": [
            {"id": "loader:orders", "type": "loader", "data": {"label": "orders"}},
            {"id": "field:profit_value", "type": "field", "data": {"label": "profit"}},
        ],
        "edges": [],
    }
    config = VizObserverConfig(output_path=str(events_path), snapshot_path=str(snapshot_path), trace_enabled=True, payload_policy="summary")
    observer = VizObserver(config=config, snapshot=snapshot)
    observer.run_id = "run_norm"
    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer.on_loader_call(event_envelope(LoaderCallEvent(loader_name="orders [preload_forever]", params={}, result=[], duration=0.0)))
    observer.on_field_compute(event_envelope(FieldComputeEvent(field_key="profit", row_id=1, dependencies={}, result=None)))
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))

    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    loader_events = [evt for evt in events if evt["event_type"] == "loader_called"]
    assert loader_events
    assert loader_events[0]["node_ref"]["id"] == "loader:orders"
    assert loader_events[0]["payload"].get("loader_display_name") == "orders [preload_forever]"

    trace_events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    compute_events = [evt for evt in trace_events if evt["event_type"] == "field_computed"]
    assert compute_events
    assert compute_events[0]["node_ref"]["id"] == "field:profit_value"


def test_viz_loader_call_summary_includes_chunk_offset(tmp_path: Path) -> None:
    events_path = tmp_path / "viz_events.jsonl"
    config = VizObserverConfig(output_path=str(events_path), payload_policy="summary")
    observer = VizObserver(config=config, snapshot={"meta": {}})
    observer.run_id = "run_chunk_offset"
    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer.on_loader_call(
        event_envelope(
            LoaderCallEvent(
                loader_name="orders",
                params={},
                result={"1": {"name": "a"}},
                duration=0.01,
                lookup_key_count=2,
                chunk_offset=40,
            )
        )
    )
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))

    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    loader_events = [evt for evt in events if evt["event_type"] == "loader_called"]
    assert loader_events
    assert loader_events[0]["payload"]["chunk_offset"] == 40
    assert loader_events[0]["payload"]["lookup_key_count"] == 2


def test_viz_payload_policy_none_and_full(tmp_path: Path) -> None:
    events_path = tmp_path / "events_none.jsonl"
    config = VizObserverConfig(output_path=str(events_path), payload_policy="none")
    observer = VizObserver(config=config, snapshot={"meta": {}})
    observer.run_id = "run_payload_none"
    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer.close()
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert events
    assert events[0]["payload"] == {}

    events_path_full = tmp_path / "events_full.jsonl"
    config_full = VizObserverConfig(output_path=str(events_path_full), payload_policy="full")
    observer_full = VizObserver(config=config_full, snapshot={"meta": {}})
    observer_full.run_id = "run_payload_full"
    observer_full.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer_full.close()
    events = [json.loads(line) for line in events_path_full.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert events
    assert "data" in events[0]["payload"]


def test_viz_observer_additional_coverage(tmp_path: Path) -> None:
    config = VizObserverConfig(snapshot_path=str(tmp_path / "snapshot_only.json"))
    events_path, snapshot_path, trace_path = config.resolve_output_paths()
    assert events_path is None
    assert snapshot_path.endswith("snapshot_only.json")
    assert trace_path.endswith("viz_trace.jsonl")

    config = VizObserverConfig(output_path=str(tmp_path / "events.jsonl"), trace_path=str(tmp_path / "trace_explicit.jsonl"))
    _, _, trace_path = config.resolve_output_paths()
    assert trace_path.endswith("trace_explicit.jsonl")

    config_disabled = VizObserverConfig()
    observer_disabled = VizObserver(config=config_disabled, snapshot={"meta": {}})
    observer_disabled._emit_to(None, "noop", {"type": "pipeline", "id": "pipeline"}, {})
    observer_disabled._emit_trace("noop", {"type": "pipeline", "id": "pipeline"}, {})
    observer_disabled.on_relation_lookup(
        event_envelope(
            RelationLookupEvent(
                field_key="profit",
                row_id=1,
                fk_raw="1",
                fk_normalized=1,
                target_source="orders",
                result="hit",
                fk_type="str",
                expected_type="int",
                error_message="bad key",
            )
        )
    )
    observer_disabled.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=1, duration=0.1)))
    observer_disabled.on_adaptive_scheduler_decision(
        event_envelope(
            AdaptiveSchedulerDecisionEvent(
                batch_num=1,
                layer_index=0,
                decision="process",
                backend="multiprocessing",
                reason="because",
                layer_task_count=1,
                process_failure_mode="fail_fast",
            )
        )
    )

    config_enabled = VizObserverConfig(output_path=str(tmp_path / "enabled.jsonl"))
    observer = VizObserver(config=config_enabled, snapshot={"meta": {}})
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=0, total_duration=0.0)))
    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1])))
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.0)))
    observer.on_loader_call(event_envelope(LoaderCallEvent(loader_name="orders", params={}, result=[], duration=0.0)))
    observer.on_error(event_envelope(ErrorEvent(ValueError("boom"), {"field_key": "profit"})))
    observer.on_diagnostic_warning(
        event_envelope(DiagnosticWarningEvent(message="warn", source_id="orders", field_id="profit", lookup_key="k", row_id=1))
    )
    observer.on_column_write(event_envelope(ColumnWriteEvent(field_key="profit", row_count=1, batch_num=1)))
    observer.on_field_compute(event_envelope(FieldComputeEvent(field_key="profit", row_id=1, dependencies={}, result=None)))
    observer.on_row_write(event_envelope(RowWriteEvent(row_id=1, field_count=1, batch_num=1, row_index=0)))
    observer.on_row_release(event_envelope(RowReleaseEvent(row_id=1, released_fields=[], retained_fields=[], batch_num=1)))
    observer.on_field_slim(event_envelope(FieldSlimEvent(field_key="profit", reason="done", batch_num=1, remaining_fields=0)))
    observer.on_loader_slim(event_envelope(LoaderSlimEvent(loader_name="orders", original_keys=0, extracted_fields=[], batch_num=1)))
    observer.on_relation_lookup(
        event_envelope(
            RelationLookupEvent(
                field_key="profit",
                row_id=1,
                fk_raw="1",
                fk_normalized=1,
                target_source="orders",
                result="hit",
            )
        )
    )
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=1, duration=0.1)))
    observer.on_adaptive_scheduler_decision(
        event_envelope(AdaptiveSchedulerDecisionEvent(batch_num=1, layer_index=0, decision="process", backend="multiprocessing"))
    )

    class DummyEmitter:
        def emit(self, _: Any) -> None:
            raise AssertionError("should not emit")

    observer._emit_to(None, "noop", {"type": "pipeline", "id": "pipeline"}, {})
    observer._emit_to(DummyEmitter(), "noop", {"type": "pipeline", "id": "pipeline"}, {})

    observer_without_run = VizObserver(config=config_enabled, snapshot={"meta": {}})
    observer_without_run._emit_to(DummyEmitter(), "noop", {"type": "pipeline", "id": "pipeline"}, {})

    assert VizObserver._canonical_loader_name(None) == ""
    assert observer._normalize_node_ref_id("") == ""
    assert observer._normalize_node_ref({"type": "pipeline"}) == {"type": "pipeline"}

    snapshot = {
        "meta": {},
        "nodes": [
            {"id": "loader:orders", "type": "loader", "data": {}},
            {"id": "field:profit_value", "type": "field", "data": {}},
        ],
        "edges": [],
    }
    config_paths = VizObserverConfig(
        output_dir=str(tmp_path / "runs"),
        output_path=str(tmp_path / "explicit_events.jsonl"),
        snapshot_path=str(tmp_path / "explicit_snapshot.json"),
        trace_enabled=True,
    )
    observer_paths = VizObserver(config=config_paths, snapshot=snapshot)
    observer_paths._apply_run_output_dir()
    observer_paths.run_id = "run_paths"
    observer_paths._apply_run_output_dir()
    observer_paths._apply_run_output_dir()

    config_active = VizObserverConfig(
        output_path=str(tmp_path / "events_active.jsonl"),
        snapshot_path=str(tmp_path / "snapshot_active.json"),
        trace_enabled=True,
        payload_policy="summary",
    )
    observer_active = VizObserver(config=config_active, snapshot=snapshot)
    observer_active.run_id = "run_active"
    observer_active._ensure_emitters()
    observer_active._ensure_emitters()
    observer_active._write_snapshot_if_needed()
    observer_active._write_snapshot_if_needed()
    observer_active.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    observer_active.on_loader_slim(
        event_envelope(LoaderSlimEvent(loader_name="orders [preload_forever]", original_keys=1, extracted_fields=["order_id"], batch_num=1))
    )
    observer_active.on_relation_lookup(
        event_envelope(
            RelationLookupEvent(
                field_key="profit",
                row_id=1,
                fk_raw="1",
                fk_normalized=1,
                target_source="orders",
                result="hit",
                fk_type="str",
                expected_type="int",
                error_message="bad key",
            )
        )
    )
    observer_active.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=1, duration=0.1)))
    observer_active.on_adaptive_scheduler_decision(
        event_envelope(
            AdaptiveSchedulerDecisionEvent(
                batch_num=1,
                layer_index=0,
                decision="process",
                backend="multiprocessing",
                reason="because",
                layer_task_count=1,
                process_failure_mode="fail_fast",
                pool_limits={"process": 1},
                pool_wait_ms_total={"process": 10.0},
                pool_wait_ms_max={"process": 10.0},
                pool_wait_count={"process": 1},
            )
        )
    )
    assert observer_active._normalize_node_ref_id("loader:orders [preload_forever]") == "loader:orders"
    observer_active.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))


def test_viz_pipeline_end_closes_trace_emitter_when_events_emitter_is_missing(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "trace_only_snapshot.json"
    config = VizObserverConfig(snapshot_path=str(snapshot_path), trace_enabled=True)
    observer = VizObserver(config=config, snapshot={"meta": {}})
    observer.run_id = "run_trace_only"

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    assert observer._events_emitter is None
    assert observer._trace_emitter is not None

    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=0, total_duration=0.0)))
    assert observer._events_emitter is None
    assert observer._trace_emitter is None


def test_viz_handlers_cover_optional_field_skip_branches(tmp_path: Path) -> None:
    events_path = tmp_path / "viz_optional.jsonl"
    snapshot_path = tmp_path / "viz_optional_snapshot.json"
    config = VizObserverConfig(
        output_path=str(events_path),
        snapshot_path=str(snapshot_path),
        trace_enabled=True,
        payload_policy="summary",
    )
    observer = VizObserver(config=config, snapshot={"meta": {}})
    observer.run_id = "run_optional"

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=1)))
    assert observer._events_emitter is not None
    assert observer._trace_emitter is not None

    observer.on_relation_lookup(
        event_envelope(
            RelationLookupEvent(
                field_key="profit",
                row_id=1,
                fk_raw="1",
                fk_normalized=1,
                target_source="orders",
                result="hit",
            )
        )
    )
    observer.on_adaptive_scheduler_decision(
        event_envelope(AdaptiveSchedulerDecisionEvent(batch_num=1, layer_index=0, decision="process", backend="multiprocessing"))
    )
    observer.on_output_target_end(
        event_envelope(
            OutputTargetEndEvent(
                target_id="summary",
                output_path="/tmp/demo.xlsx",
                sheet_name=None,
                row_count=10,
                error_count=0,
                duration=0.0,
                disabled=False,
                error_type=None,
                error_message=None,
            )
        )
    )
    observer.close()
