import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from scalim.events import Event, EventType
from scalim.events._events import PipelineStartEvent, WorkflowNodeEndEvent, WorkflowNodeStartEvent, WorkflowResourceCommitEvent
from scalim.execution.adaptive.capture import HookRecordedEvent
from scalim.execution import ExecutionRequest, ExportLayout, ObservabilitySpec
from scalim.hooks import BaseHook, HookManager
from scalim.ob.hub import InstrumentationHub
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.ob.presets._internal.viz_config import VizObserverConfig
from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
from scalim.workflow import execute_controller as controller_mod
from scalim.workflow import execute as execute_mod


class _RecordingHook(BaseHook):
    def __init__(self) -> None:
        self.typed: List[str] = []

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:  # type: ignore[override]
        _ = event
        self.typed.append("pipeline_start")


class _RecordingObserver(Observer):
    supports_unknown_event_types = True

    def __init__(self) -> None:
        self.event_types = None
        self.events: List[str] = []

    def on_event(self, event: Event) -> None:
        self.events.append(str(event.event_type))

    def close(self) -> None:
        self.events.append("close")


class _CaptureHookManager:
    def __init__(self, events: List[HookRecordedEvent]) -> None:
        self._events = list(events)

    def drain_events(self) -> List[HookRecordedEvent]:
        return list(self._events)


class _CaptureObserverManager:
    def __init__(self, events: List[Event]) -> None:
        self._events = list(events)

    def drain_events(self) -> List[Event]:
        return list(self._events)


def _make_workflow_ir_single_node(node_id: str) -> WorkflowIr:
    node = WorkflowNodeIr(node_id=str(node_id), node_type=WorkflowNodeType.DEMAND, decl_order=1)
    return WorkflowIr(
        nodes=(node,),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )


def test_build_demand_replay_instrumentation_returns_none_without_request_and_viz() -> None:
    hub = controller_mod._build_demand_replay_instrumentation(None, None, workflow_components=())
    assert hub is None


def test_build_demand_replay_instrumentation_returns_none_when_request_has_no_components() -> None:
    request = ExecutionRequest(export_layout=ExportLayout(field_ids=()))
    hub = controller_mod._build_demand_replay_instrumentation(request, None, workflow_components=())
    assert hub is None


def test_build_demand_replay_instrumentation_supports_request_components_without_viz_observer() -> None:
    request = ExecutionRequest(export_layout=ExportLayout(field_ids=()), components=[_RecordingObserver()])
    hub = controller_mod._build_demand_replay_instrumentation(request, None, workflow_components=())
    assert hub is not None


def test_replay_captured_workflow_observability_returns_when_replay_hub_is_missing() -> None:
    prepared = SimpleNamespace(
        capture_observability=True,
        workflow_replay_instrumentation=None,
        workflow_instrumentation=None,
        workflow_ir=_make_workflow_ir_single_node("n1"),
        workflow_exec_id="wf",
        workflow_components=(),
        captured_demand_events_by_node_id={},
        captured_demand_hook_events_by_node_id={},
        captured_demand_viz_observer_by_node_id={},
        captured_demand_request_by_node_id={},
    )
    execute_mod._replay_captured_workflow_observability(prepared)  # type: ignore[arg-type]


def test_replay_captured_workflow_observability_replays_workflow_and_demand_events() -> None:
    node_id = "n1"
    workflow_ir = _make_workflow_ir_single_node(node_id)
    workflow_exec_id = "wf_test"

    workflow_hook = _RecordingHook()
    workflow_observer = _RecordingObserver()
    replay = InstrumentationHub(
        hook_manager=HookManager(),
        observer_manager=ObserverManager(run_id=workflow_exec_id),
    )
    replay.hook_manager.register(workflow_hook)
    replay.observer_manager.register(workflow_observer)

    ts = float(time.time())
    workflow_events: List[Event] = [
        Event(event_type="workflow_started", timestamp=ts, run_id=workflow_exec_id, payload={"x": 1}, meta={}, seq=1),
        Event(
            event_type=EventType.WORKFLOW_RESOURCE_COMMIT,
            timestamp=ts,
            run_id=workflow_exec_id,
            payload=WorkflowResourceCommitEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id="__wf__commit",
                resource_type="csv",
                resource_id="r",
                path="/tmp/out.csv",
            ),
            meta={},
            seq=2,
        ),
        Event(
            event_type=EventType.WORKFLOW_NODE_START,
            timestamp=ts,
            run_id=workflow_exec_id,
            payload=WorkflowNodeStartEvent(workflow_exec_id=workflow_exec_id, workflow_node_id=node_id, node_type="demand"),
            meta={"workflow_node_id": node_id},
            seq=3,
        ),
        Event(
            event_type=EventType.WORKFLOW_NODE_END,
            timestamp=ts,
            run_id=workflow_exec_id,
            payload=WorkflowNodeEndEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id=node_id,
                node_type="demand",
                status="ok",
            ),
            meta={"workflow_node_id": node_id},
            seq=4,
        ),
        Event(event_type="some_global_event", timestamp=ts, run_id=workflow_exec_id, payload={"g": 1}, meta={"x": "y"}, seq=5),
        Event(
            event_type="some_node_event",
            timestamp=ts,
            run_id=workflow_exec_id,
            payload={"n": 1},
            meta={"workflow_node_id": "unknown"},
            seq=6,
        ),
        Event(event_type="workflow_finished", timestamp=ts, run_id=workflow_exec_id, payload={"x": 2}, meta={}, seq=7),
    ]
    workflow_hook_events = [
        HookRecordedEvent(event_type=EventType.PIPELINE_START, payload=PipelineStartEvent(targets=[], batch_size=None)),
    ]

    extra_hook = _RecordingHook()
    extra_observer = _RecordingObserver()
    viz_observer = _RecordingObserver()
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=()),
        observability=ObservabilitySpec(fallback_logger_enabled=True),
        components=[workflow_hook, workflow_observer, extra_hook, extra_observer],
    )

    demand_hook_events = [
        HookRecordedEvent(event_type=EventType.PIPELINE_START, payload=PipelineStartEvent(targets=[], batch_size=None)),
    ]
    demand_observer_events = [
        Event(
            event_type=EventType.PIPELINE_START,
            timestamp=ts,
            run_id=node_id,
            payload=PipelineStartEvent(targets=[], batch_size=None),
            meta={},
            seq=2,
        ),
        Event(
            event_type=EventType.PIPELINE_START,
            timestamp=ts,
            run_id=node_id,
            payload=PipelineStartEvent(targets=[], batch_size=None),
            meta={},
            seq=1,
        ),
    ]

    capture = SimpleNamespace(
        hook_manager=_CaptureHookManager(workflow_hook_events),
        observer_manager=_CaptureObserverManager(workflow_events),
    )
    prepared = SimpleNamespace(
        capture_observability=True,
        workflow_replay_instrumentation=replay,
        workflow_instrumentation=capture,
        workflow_ir=workflow_ir,
        workflow_exec_id=workflow_exec_id,
        workflow_components=(workflow_hook, workflow_observer),
        captured_demand_events_by_node_id={node_id: list(demand_observer_events)},
        captured_demand_hook_events_by_node_id={node_id: list(demand_hook_events)},
        captured_demand_viz_observer_by_node_id={node_id: viz_observer},
        captured_demand_request_by_node_id={node_id: request},
    )
    execute_mod._replay_captured_workflow_observability(prepared)  # type: ignore[arg-type]

    assert "pipeline_start" in workflow_hook.typed
    assert "workflow_started" in workflow_observer.events
    assert "workflow_finished" in workflow_observer.events
    assert "close" in viz_observer.events
    assert "pipeline_start" in extra_hook.typed


def test_build_workflow_instrumentation_closes_manager_on_error(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> Dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(execute_mod, "build_workflow_viz_graph_snapshot", _boom)
    workflow_ir = _make_workflow_ir_single_node("n1")
    with pytest.raises(RuntimeError, match="boom"):
        _ = execute_mod._build_workflow_instrumentation(
            workflow_exec_id="wf",
            workflow_path=str(tmp_path / "wf.yaml"),
            workflow_ir=workflow_ir,
            components=None,
            bundle_viz_base_config=VizObserverConfig(output_dir=str(tmp_path)),
        )
