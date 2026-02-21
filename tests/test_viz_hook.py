# region imports

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scalim.events.events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowReleaseEvent,
    RowWriteEvent,
)
from scalim.ob.presets import viz as viz_module
from scalim.ob.presets.viz import VizEventEmitter, VizObserver, VizObserverConfig

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


def test_viz_helpers_and_config_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(viz_module.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    win_dir = viz_module._default_viz_dir()
    assert win_dir.endswith(os.path.join("appdata", "scalim-viz"))

    monkeypatch.setattr(viz_module.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    darwin_dir = viz_module._default_viz_dir()
    assert "Application Support" in darwin_dir
    assert darwin_dir.endswith(os.path.join("Application Support", "scalim-viz"))

    monkeypatch.setattr(viz_module.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    linux_dir = viz_module._default_viz_dir()
    assert linux_dir.endswith(os.path.join("xdg", "scalim-viz"))

    assert viz_module._normalize_output_dir(str(tmp_path / "run-root")).endswith("scalim-viz")
    assert viz_module._normalize_output_dir(str(tmp_path / "scalim-viz")) == os.path.normpath(str(tmp_path / "scalim-viz"))
    assert viz_module._normalize_output_dir(str(tmp_path / "scalim-viz" / "run1")) == os.path.normpath(
        str(tmp_path / "scalim-viz" / "run1")
    )

    assert viz_module._safe_len([1, 2]) == 2
    assert viz_module._safe_len(5) == 0
    assert viz_module._safe_len(BrokenLen()) == 0

    assert viz_module._sample_value(None, 1) is None
    assert viz_module._sample_value([1, 2, 3], 2) == [1, 2]
    assert viz_module._sample_value((1, 2, 3), 2) == [1, 2]
    assert viz_module._sample_value({"a": 1, "b": 2}, 1) == {"a": 1}
    assert viz_module._sample_value({"a": {"b": 1}}, 1) == {"a": {"b": 1}}
    assert viz_module._sample_value(set([1, 2, 3]), 1)
    assert viz_module._sample_value("abc", 2) == "abc"
    assert viz_module._sample_value([1, 2, 3], 0) is None

    local = VizObserverConfig.default_local()
    assert local.output_dir

    monkeypatch.setattr(viz_module.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "default"))
    config = VizObserverConfig(use_default_output_dir=True)
    events_path, snapshot_path = config.resolve_output_paths()
    assert events_path.endswith(os.path.join("scalim-viz", "viz_events.jsonl"))
    assert snapshot_path.endswith(os.path.join("scalim-viz", "viz_snapshot.json"))

    monkeypatch.setenv("HOME", str(tmp_path))
    config = VizObserverConfig(output_path="~/events.jsonl", snapshot_path="~/snapshot.json")
    events_path, snapshot_path = config.resolve_output_paths()
    assert str(tmp_path) in events_path
    assert str(tmp_path) in snapshot_path

    config = VizObserverConfig(output_dir=str(tmp_path / "runs"), events_filename="evt.jsonl", snapshot_filename="snap.json")
    events_path, snapshot_path = config.resolve_output_paths()
    assert events_path.endswith(os.path.join("scalim-viz", "evt.jsonl"))
    assert snapshot_path.endswith(os.path.join("scalim-viz", "snap.json"))


def test_viz_event_emitter_success_and_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = DummyLogger()
    out_path = tmp_path / "events" / "viz_events.jsonl"
    config = VizObserverConfig(output_path=str(out_path), logger=logger)

    emitter = VizEventEmitter(config)
    emitter.emit({"ok": True})
    emitter.close()
    text = out_path.read_text(encoding="utf-8").strip()
    assert '"ok": true' in text
    assert emitter._output_handle is None

    emitter = VizEventEmitter(config)
    emitter._output_handle = BrokenHandle()
    emitter.emit({"ok": True})
    assert logger.messages
    emitter._output_handle = None
    emitter.close()

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("fail open")

    monkeypatch.setattr(Path, "open", boom)
    emitter = VizEventEmitter(config)
    assert emitter._output_handle is None


def test_viz_observer_hook_emits_events(tmp_path: Path) -> None:
    output_path = tmp_path / "viz.jsonl"
    snapshot = {"meta": "invalid"}
    config = VizObserverConfig(
        output_path=str(output_path),
        event_mode="full",
        payload_policy="sample",
        sample_size=1,
        run_name="demo",
        env="dev",
    )
    hook = VizObserver(config=config, snapshot=snapshot)

    hook._ensure_run_id()
    hook._ensure_run_id()

    hook.on_pipeline_start(PipelineStartEvent(targets=["profit"], batch_size=10))
    hook.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2, 3]))
    hook.on_loader_call(
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
    hook.on_field_compute(FieldComputeEvent(field_key="profit", row_id=1, dependencies={"a": 1}, result=10))
    hook.on_error(ErrorEvent(ValueError("boom"), {"field_key": "profit", "row_id": 1}))
    hook.on_diagnostic_warning(
        DiagnosticWarningEvent(
            message="float lookup key",
            source_id="orders",
            field_id="profit",
            lookup_key="1001.0",
            row_id=1,
        )
    )
    hook.on_column_write(ColumnWriteEvent(field_key="profit", row_count=2, batch_num=1))
    hook.on_row_write(RowWriteEvent(row_id=1, field_count=2, batch_num=1, row_index=0))
    hook.on_row_release(RowReleaseEvent(row_id=1, released_fields=["a"], retained_fields=["b"], batch_num=1))
    hook.on_field_slim(FieldSlimEvent(field_key="profit", reason="done", batch_num=1, remaining_fields=0))
    hook.on_loader_slim(LoaderSlimEvent(loader_name="orders", original_keys=2, extracted_fields=["order_id"], batch_num=1))
    hook.on_batch_end(BatchEndEvent(batch_num=1, duration=0.02))
    hook.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.3))

    data = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    event_types = {evt["event_type"] for evt in data}
    assert "run_started" in event_types
    assert "run_finished" in event_types
    assert "error" in event_types
    assert "diagnostic_warning" in event_types
    assert "row_written" in event_types


def test_viz_observer_hook_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = VizObserver()

    class DummyPlan:
        def to_viz_graph_snapshot(self) -> dict:
            return {"meta": {}}

    _ = VizObserver.from_plan(DummyPlan(), VizObserverConfig(output_path=str(tmp_path / "plan.jsonl")))

    disabled = VizObserver(config=VizObserverConfig())
    disabled._emit("run_started", {"type": "pipeline", "id": "pipeline"}, {})
    disabled.on_pipeline_start(PipelineStartEvent(targets=["profit"], batch_size=1))
    disabled.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.1))
    disabled.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    disabled.on_batch_end(BatchEndEvent(batch_num=1, duration=0.1))
    disabled.on_loader_call(LoaderCallEvent(loader_name="orders", params={}, result=[], duration=0.0))
    disabled.on_field_compute(FieldComputeEvent(field_key="profit", row_id=1, dependencies={}, result=None))
    disabled.on_error(ErrorEvent(ValueError("boom"), {"field_key": "profit"}))
    disabled.on_diagnostic_warning(DiagnosticWarningEvent(message="warn", source_id="orders", field_id="profit", lookup_key="k", row_id=1))
    disabled.on_column_write(ColumnWriteEvent(field_key="profit", row_count=1, batch_num=1))
    disabled.on_row_write(RowWriteEvent(row_id=1, field_count=1, batch_num=1, row_index=0))
    disabled.on_row_release(RowReleaseEvent(row_id=1, released_fields=[], retained_fields=[], batch_num=1))
    disabled.on_field_slim(FieldSlimEvent(field_key="profit", reason="done", batch_num=1, remaining_fields=0))
    disabled.on_loader_slim(LoaderSlimEvent(loader_name="orders", original_keys=0, extracted_fields=[], batch_num=1))

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events0.jsonl")))
    hook.run_id = "run_0"
    hook._emit("run_started", {"type": "pipeline", "id": "pipeline"}, {})
    hook._emitter = VizEventEmitter(hook.config)
    hook.run_id = None
    hook._emit("run_started", {"type": "pipeline", "id": "pipeline"}, {})
    hook.run_id = "run_0"
    hook.config.event_mode = "lite"
    hook._emit("row_written", {"type": "batch", "id": "batch:1"}, {})

    config = VizObserverConfig(output_dir=str(tmp_path))
    hook = VizObserver(config=config, snapshot={"meta": {}})
    hook._write_snapshot_if_needed()
    hook._snapshot_written = True
    hook._write_snapshot_if_needed()

    hook.run_id = "run_1"
    hook._apply_run_output_dir()
    assert hook.config.output_dir
    assert hook.config.output_dir.endswith("run_1")
    hook._run_dir_applied = True
    hook._apply_run_output_dir()

    hook = VizObserver(config=VizObserverConfig(output_dir=None, use_default_output_dir=False))
    hook._apply_run_output_dir()

    monkeypatch.setattr(viz_module.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "default"))
    hook = VizObserver(config=VizObserverConfig(output_dir=None, use_default_output_dir=True))
    hook.run_id = "run_2"
    hook._apply_run_output_dir()
    assert hook.config.output_dir.endswith("run_2")

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events_path.jsonl")))
    hook.run_id = "run_3"
    hook._apply_run_output_dir()
    assert hook.config.output_dir is None

    hook = VizObserver(config=VizObserverConfig(output_dir=str(tmp_path / "base_explicit"), output_path=str(tmp_path / "explicit.jsonl")))
    hook.run_id = "run_4"
    hook._apply_run_output_dir()
    assert hook._run_dir_applied is True

    hook._emitter = None
    hook._ensure_emitter()
    hook._ensure_emitter()
    assert hook._emitter is not None

    config = VizObserverConfig(output_path=str(tmp_path / "events.jsonl"))
    hook = VizObserver(config=config, snapshot={"meta": {}})
    hook.run_id = "run_1"
    hook._apply_run_output_dir()
    assert hook.config.output_dir is None

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events2.jsonl"), event_mode="lite"))
    hook.on_pipeline_start(PipelineStartEvent(targets=["profit"], batch_size=1))
    hook.on_row_write(RowWriteEvent(row_id=1, field_count=2, batch_num=1, row_index=0))
    events = [json.loads(line) for line in (tmp_path / "events2.jsonl").read_text(encoding="utf-8").splitlines()]
    event_types = {evt["event_type"] for evt in events}
    assert "row_written" not in event_types

    hook_no_emitter = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events_no_emitter.jsonl")))
    hook_no_emitter.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.1))
    hook_no_emitter.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    hook_no_emitter.on_batch_end(BatchEndEvent(batch_num=1, duration=0.1))
    hook_no_emitter.on_loader_call(LoaderCallEvent(loader_name="orders", params={}, result=[], duration=0.0))
    hook_no_emitter.on_field_compute(FieldComputeEvent(field_key="profit", row_id=1, dependencies={}, result=None))
    hook_no_emitter.on_error(ErrorEvent(ValueError("boom"), {"field_key": "profit"}))
    hook_no_emitter.on_diagnostic_warning(
        DiagnosticWarningEvent(message="warn", source_id="orders", field_id="profit", lookup_key="k", row_id=1)
    )
    hook_no_emitter.on_column_write(ColumnWriteEvent(field_key="profit", row_count=1, batch_num=1))
    hook_no_emitter.on_row_write(RowWriteEvent(row_id=1, field_count=1, batch_num=1, row_index=0))
    hook_no_emitter.on_row_release(RowReleaseEvent(row_id=1, released_fields=[], retained_fields=[], batch_num=1))
    hook_no_emitter.on_field_slim(FieldSlimEvent(field_key="profit", reason="done", batch_num=1, remaining_fields=0))
    hook_no_emitter.on_loader_slim(LoaderSlimEvent(loader_name="orders", original_keys=0, extracted_fields=[], batch_num=1))

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events3.jsonl"), payload_policy="none"))
    hook.on_pipeline_start(PipelineStartEvent(targets=["profit"], batch_size=1))
    events = [json.loads(line) for line in (tmp_path / "events3.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[0]["payload"] == {}

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events4.jsonl"), payload_policy="full"))
    hook.on_pipeline_start(PipelineStartEvent(targets=["profit"], batch_size=1))
    events = [json.loads(line) for line in (tmp_path / "events4.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "data" in events[0]["payload"]

    hook = VizObserver(config=VizObserverConfig(output_path=str(tmp_path / "events6.jsonl")))
    hook.on_pipeline_start(PipelineStartEvent(targets=["profit"], batch_size=1))
    hook.on_error(ErrorEvent(ValueError("boom"), {"loader_name": "orders"}))
    hook.on_error(ErrorEvent(ValueError("boom"), {"source_id": "orders"}))
    hook.on_error(ErrorEvent(ValueError("boom"), {}))

    hook = VizObserver(config=VizObserverConfig(output_dir=str(tmp_path / "base"), use_default_output_dir=True), snapshot=None)
    hook._write_snapshot_if_needed()

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("fail write")

    monkeypatch.setattr(Path, "open", boom)
    hook = VizObserver(
        config=VizObserverConfig(output_path=str(tmp_path / "events5.jsonl"), snapshot_path=str(tmp_path / "snap.json")),
        snapshot={"meta": {}},
    )
    hook._write_snapshot_if_needed()
