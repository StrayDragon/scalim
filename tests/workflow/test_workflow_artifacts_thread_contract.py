import pytest

from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
from scalim.workflow.artifacts import WorkflowArtifactsDirectory


def _make_artifacts_dir() -> WorkflowArtifactsDirectory:
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=2, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    return WorkflowArtifactsDirectory(workflow_ir)


def test_workflow_artifacts_directory_mutating_helpers_require_controller_thread() -> None:
    artifacts_dir = _make_artifacts_dir()
    artifacts_dir._owner_thread_id = -1  # noqa: SLF001

    calls = [
        lambda: artifacts_dir.discard_in_memory_csv_output("r1", "detail"),
        lambda: artifacts_dir.discard_all_in_memory_csv_outputs(),
        lambda: artifacts_dir.discard_all_in_memory_rows(),
        lambda: artifacts_dir.discard_in_memory_rows_output("r1", "detail"),
        lambda: artifacts_dir.discard_all_in_memory_rows_outputs(),
    ]
    for call in calls:
        with pytest.raises(RuntimeError, match="WorkflowArtifactsDirectory write must be called from controller thread"):
            call()
