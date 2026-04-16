from typing import Any, Dict, List, Optional, Tuple

import pytest

from scalim.execution import ExecutionRequest, ExecutionResult, ExportLayout
from scalim.planning.plan import ExecutionPlan
from scalim.sinks.rows import InMemoryRows
from scalim.spec.ir import DemandIr, MainSourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr
from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
from scalim.workflow.errors import ScalimWorkflowConfigError
from scalim.workflow.execute import run_workflow_ir


class _Compilation(object):
    def __init__(self, demand_ir: DemandIr, request: ExecutionRequest) -> None:
        self.demand_ir = demand_ir
        self.request = request


def _make_base_request() -> ExecutionRequest:
    return ExecutionRequest(export_layout=ExportLayout(field_ids=("x",)))


def test_workflow_main_rows_capture_and_release_are_scoped_and_deterministic(monkeypatch: Any) -> None:
    # A produces typed rows; C and D consume via `main_rows_from_run_id=A`; B is unrelated.
    node_a = WorkflowNodeIr(node_id="A", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yml")
    node_b = WorkflowNodeIr(node_id="B", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=(), demand_path="b.yml")
    node_c = WorkflowNodeIr(
        node_id="C",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=2,
        deps=("A",),
        demand_path="c.yml",
        main_rows_from_run_id="A",
    )
    node_d = WorkflowNodeIr(
        node_id="D",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=3,
        deps=("A",),
        demand_path="d.yml",
        main_rows_from_run_id="A",
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, node_b, node_c, node_d),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    demand_ir = DemandIr(
        sources={},
        fields={},
        main_source=MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader")),
    )

    def _compile_demand_fn(_path: str, **_kwargs: Any) -> _Compilation:
        return _Compilation(demand_ir=demand_ir, request=_make_base_request())

    seq: List[Tuple[str, str, object]] = []

    import scalim.workflow.execute as workflow_execute  # noqa: PLC0415

    real_discard = workflow_execute.WorkflowArtifactsDirectory.discard

    def _spy_discard(self: Any, producer_node_id: str, artifact_id: str) -> None:
        seq.append(("artifact", "discard", (str(producer_node_id), str(artifact_id))))
        real_discard(self, producer_node_id, artifact_id)

    monkeypatch.setattr(workflow_execute.WorkflowArtifactsDirectory, "discard", _spy_discard)

    calls: List[Dict[str, object]] = []

    def _run_ir_stub(_demand_ir: DemandIr, request: ExecutionRequest, **kwargs: Any) -> ExecutionResult:
        meta = kwargs.get("event_meta_defaults") or {}
        node_id = str(meta.get("workflow_node_id") or "")
        main_rows = None
        if request.main_rows is not None:
            main_rows = list(request.main_rows)
        calls.append(
            {
                "node_id": node_id,
                "capture_in_memory_rows": bool(request.capture_in_memory_rows),
                "main_rows": main_rows,
            }
        )
        seq.append(("run_ir", str(node_id), bool(request.capture_in_memory_rows)))

        in_memory_rows = None
        if request.capture_in_memory_rows:
            in_memory_rows = InMemoryRows(header=["x"], rows=[[1], [2]])

        return ExecutionResult(
            output_path=None,
            total_rows=0,
            duration=0.0,
            demand_ir=_demand_ir,
            plan=ExecutionPlan(),
            outputs={},
            in_memory_rows=in_memory_rows,
        )

    result = run_workflow_ir(
        workflow_path="wf.yml",
        workflow_ir=workflow_ir,
        compile_demand_fn=_compile_demand_fn,
        run_ir_fn=_run_ir_stub,
        components=None,
    )

    calls_by_node_id = {str(item["node_id"]): item for item in calls}

    assert calls_by_node_id["A"]["capture_in_memory_rows"] is True
    assert calls_by_node_id["A"]["main_rows"] is None

    assert calls_by_node_id["B"]["capture_in_memory_rows"] is False
    assert calls_by_node_id["B"]["main_rows"] is None

    expected_main_rows = [{"x": 1}, {"x": 2}]
    assert calls_by_node_id["C"]["capture_in_memory_rows"] is False
    assert calls_by_node_id["C"]["main_rows"] == expected_main_rows
    assert calls_by_node_id["D"]["capture_in_memory_rows"] is False
    assert calls_by_node_id["D"]["main_rows"] == expected_main_rows

    # Only discard after the last consumer finished.
    run_nodes = [item for item in seq if item[0] == "run_ir"]
    discard_ops = [item for item in seq if item[0] == "artifact" and item[1] == "discard"]
    assert [n[1] for n in run_nodes] == ["A", "B", "C", "D"]
    assert discard_ops == [("artifact", "discard", ("A", "in_memory_rows"))]

    outcomes_by_run_id = {o.run_id: o for o in result.outcomes}
    assert outcomes_by_run_id["A"].error is None
    assert outcomes_by_run_id["B"].error is None
    assert outcomes_by_run_id["C"].error is None
    assert outcomes_by_run_id["D"].error is None

    assert isinstance(outcomes_by_run_id["A"].result, ExecutionResult)
    assert outcomes_by_run_id["A"].result.in_memory_rows is not None
    assert outcomes_by_run_id["B"].result.in_memory_rows is None


def test_workflow_main_rows_visibility_error_has_diagnostic_path() -> None:
    node_a = WorkflowNodeIr(node_id="A", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yml")
    node_c = WorkflowNodeIr(
        node_id="C",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=1,
        deps=(),  # missing deps to A
        demand_path="c.yml",
        main_rows_from_run_id="A",
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, node_c),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    demand_ir = DemandIr(
        sources={},
        fields={},
        main_source=MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader")),
    )

    def _compile_demand_fn(_path: str, **_kwargs: Any) -> _Compilation:
        return _Compilation(demand_ir=demand_ir, request=_make_base_request())

    def _run_ir_stub(_demand_ir: DemandIr, request: ExecutionRequest, **_kwargs: Any) -> ExecutionResult:
        return ExecutionResult(
            output_path=None,
            total_rows=0,
            duration=0.0,
            demand_ir=_demand_ir,
            plan=ExecutionPlan(),
            outputs={},
            in_memory_rows=InMemoryRows(header=["x"], rows=[[1]]) if request.capture_in_memory_rows else None,
        )

    with pytest.raises(ScalimWorkflowConfigError) as excinfo:
        _ = run_workflow_ir(
            workflow_path="wf.yml",
            workflow_ir=workflow_ir,
            compile_demand_fn=_compile_demand_fn,
            run_ir_fn=_run_ir_stub,
            components=None,
        )

    assert excinfo.value.path == "workflow.runs.1.main_rows_from_run_id"
