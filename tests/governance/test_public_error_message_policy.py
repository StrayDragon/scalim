from pathlib import Path
from typing import List, Optional

import pytest

from scalim.events import EVENT_WORKFLOW_NODE_END, Event
from scalim.exceptions import REDACTED_ERROR_MESSAGE, ScalimError, safe_error_message
from scalim.ob.observer import Observer
from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
from scalim.workflow import execute as execute_mod


class _CollectingObserver(Observer):
    supports_unknown_event_types = True

    def __init__(self) -> None:
        self.event_types = None
        self.events: List[Event] = []

    def on_event(self, event: Event) -> None:
        self.events.append(event)


def _make_single_node_workflow_ir(*, node_id: str, demand_path: str, failure_policy: str) -> WorkflowIr:
    node = WorkflowNodeIr(
        node_id=str(node_id),
        node_type=WorkflowNodeType.DEMAND,
        decl_order=0,
        deps=(),
        demand_path=str(demand_path),
    )
    return WorkflowIr(
        nodes=(node,),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy=str(failure_policy)),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={str(node_id): ()}),
    )


def _last_workflow_node_end(observer: _CollectingObserver) -> Optional[Event]:
    for event in reversed(observer.events):
        if str(event.event_type) == EVENT_WORKFLOW_NODE_END:
            return event
    return None


def test_workflow_public_error_message_is_redacted_by_default(tmp_path: Path) -> None:
    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text("workflow: {}\n", encoding="utf-8")

    observer = _CollectingObserver()
    workflow_ir = _make_single_node_workflow_ir(
        node_id="a",
        demand_path=str(tmp_path / "demand.yaml"),
        failure_policy="primary_only",
    )

    def _compile_demand(*args: object, **kwargs: object) -> object:
        _ = args, kwargs
        raise ValueError("secret=123")

    result = execute_mod.run_workflow_ir(
        str(wf_path),
        workflow_ir,
        compile_demand_fn=_compile_demand,
        components=[observer],
    )

    assert len(result.outcomes) == 1
    assert result.outcomes[0].error is not None
    assert result.outcomes[0].error.exc_type == "ValueError"
    assert result.outcomes[0].error.message == "(redacted)"

    node_end = _last_workflow_node_end(observer)
    assert node_end is not None
    payload = node_end.payload
    assert getattr(payload, "error_type") == "ValueError"
    assert getattr(payload, "error_message") == "(redacted)"


def test_workflow_public_error_message_can_be_full_when_debug_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_DEBUG_ERRORS", "1")

    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text("workflow: {}\n", encoding="utf-8")

    observer = _CollectingObserver()
    workflow_ir = _make_single_node_workflow_ir(
        node_id="a",
        demand_path=str(tmp_path / "demand.yaml"),
        failure_policy="primary_only",
    )

    def _compile_demand(*args: object, **kwargs: object) -> object:
        _ = args, kwargs
        raise ValueError("secret=123")

    result = execute_mod.run_workflow_ir(
        str(wf_path),
        workflow_ir,
        compile_demand_fn=_compile_demand,
        components=[observer],
    )

    assert len(result.outcomes) == 1
    assert result.outcomes[0].error is not None
    assert result.outcomes[0].error.message == "secret=123"

    node_end = _last_workflow_node_end(observer)
    assert node_end is not None
    payload = node_end.payload
    assert getattr(payload, "error_message") == "secret=123"


def test_safe_error_message_handles_bad_str() -> None:
    class _BadStr(ScalimError):
        def __str__(self) -> str:
            raise RuntimeError("boom")

    assert safe_error_message(_BadStr("secret=123")) == REDACTED_ERROR_MESSAGE
