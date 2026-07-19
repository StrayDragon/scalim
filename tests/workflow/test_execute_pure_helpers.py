from scalim.events import Event, EventType
from scalim.events._events import WorkflowResourceCommitEvent
from scalim.workflow._internal.replay_event_classification import classify_workflow_events_for_replay
from scalim.workflow.outcome_builder import build_outcome_from_exception
from scalim.workflow.resources_base import ScalimWorkflowWriteError


def test_build_workflow_run_error_and_outcome_preserves_diff_for_write_error() -> None:
    exc = ScalimWorkflowWriteError("boom", diff=["a", "b"])
    outcome = build_outcome_from_exception(exc, run_id="r1", demand_path="d1")
    assert outcome.run_id == "r1"
    assert outcome.demand_path == "d1"
    assert outcome.result is None
    err = outcome.error
    assert err is not None
    assert err.run_id == "r1"
    assert err.demand_path == "d1"
    assert err.diff == ["a", "b"]


def test_classify_workflow_events_for_replay_buckets() -> None:
    events = [
        Event(event_type=EventType.WORKFLOW_STARTED, timestamp=0.0, run_id="wf", payload=None, meta={}, seq=1),
        Event(
            event_type=EventType.WORKFLOW_NODE_START,
            timestamp=0.0,
            run_id="wf",
            payload=None,
            meta={"workflow_node_id": "n1"},
            seq=2,
        ),
        Event(
            event_type="custom_node_event",
            timestamp=0.0,
            run_id="wf",
            payload=None,
            meta={"workflow_node_id": "n1"},
            seq=3,
        ),
        Event(
            event_type=EventType.WORKFLOW_NODE_END,
            timestamp=0.0,
            run_id="wf",
            payload=None,
            meta={"workflow_node_id": "n1"},
            seq=4,
        ),
        Event(
            event_type=EventType.WORKFLOW_NODE_START,
            timestamp=0.0,
            run_id="wf",
            payload=None,
            meta={"workflow_node_id": "unknown"},
            seq=5,
        ),
        Event(event_type="no_node_meta", timestamp=0.0, run_id="wf", payload=None, meta={"x": 1}, seq=6),
        Event(
            event_type=EventType.WORKFLOW_RESOURCE_COMMIT,
            timestamp=0.0,
            run_id="wf",
            payload=WorkflowResourceCommitEvent(
                workflow_exec_id="wf",
                workflow_node_id="n1",
                resource_type="workbook",
                resource_id="r1",
                path="/tmp/out.xlsx",
            ),
            meta={},
            seq=7,
        ),
        Event(event_type=EventType.WORKFLOW_FINISHED, timestamp=0.0, run_id="wf", payload=None, meta={}, seq=8),
    ]

    buckets = classify_workflow_events_for_replay(events, known_node_ids={"n1"})
    assert buckets.started_events == [events[0]]
    assert buckets.finished_events == [events[-1]]
    assert buckets.resource_commit_events == [events[6]]
    assert buckets.other_global_events == [events[5]]
    assert buckets.unknown_node_events == [events[4]]
    assert buckets.node_start_events_by_node_id["n1"] == [events[1]]
    assert buckets.node_end_events_by_node_id["n1"] == [events[3]]
    assert buckets.node_other_events_by_node_id["n1"] == [events[2]]
