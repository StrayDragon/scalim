from typing import Dict, Tuple

import pytest

from scalim.spec.ir._workflow import (
    WorkflowArtifactsIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
)
from scalim.workflow.execute import WorkflowArtifactsDirectory, WorkflowCtxStore
from scalim.workflow.errors import ScalimWorkflowConfigError
from scalim.workflow.visibility_index import WorkflowVisibilityIndex


def test_workflow_visibility_index_transitive_closure() -> None:
    deps_by_node_id: Dict[str, Tuple[str, ...]] = {
        "A": (),
        "B": ("A",),
        "C": ("B",),
    }
    index = WorkflowVisibilityIndex.build(deps_by_node_id=deps_by_node_id)
    assert index.visible_producer_node_ids("A") == frozenset()
    assert index.visible_producer_node_ids("B") == frozenset({"A"})
    assert index.visible_producer_node_ids("C") == frozenset({"A", "B"})
    assert index.visible_producer_node_ids("unknown") == frozenset()


def test_workflow_visibility_index_rejects_unknown_deps_and_cycles() -> None:
    with pytest.raises(ValueError, match="depends_on unknown node"):
        _ = WorkflowVisibilityIndex.build(deps_by_node_id={"A": ("missing",)})

    with pytest.raises(ValueError, match="cycle detected"):
        _ = WorkflowVisibilityIndex.build(deps_by_node_id={"A": ("B",), "B": ("A",)})


def test_workflow_visibility_index_rejects_blank_and_duplicate_and_blank_deps() -> None:
    from scalim.workflow import visibility_index as visibility_index_mod

    with pytest.raises(ValueError, match="non-empty string"):
        _ = WorkflowVisibilityIndex.build(deps_by_node_id={"": ()})

    with pytest.raises(ValueError, match="duplicated"):
        _ = WorkflowVisibilityIndex.build(deps_by_node_id={"A": (), " A ": ()})

    with pytest.raises(ValueError, match="non-empty string"):
        _ = visibility_index_mod._normalize_workflow_deps(deps_by_node_id={"": ("A",)})  # noqa: SLF001

    with pytest.raises(ValueError, match="deps must contain only non-empty strings"):
        _ = WorkflowVisibilityIndex.build(deps_by_node_id={"A": ("",)})


def test_workflow_ctx_and_artifacts_share_visibility_rules_transitively() -> None:
    node_a = WorkflowNodeIr(node_id="A", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=())
    node_b = WorkflowNodeIr(node_id="B", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=("A",))
    node_c = WorkflowNodeIr(
        node_id="C",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=2,
        deps=("B",),
        init_vars={"x": {"$ctx": {"node": "A", "key": "k"}}},
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, node_b, node_c),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)
    ctx_store = WorkflowCtxStore(workflow_ir)

    # transitive visibility: C -> B -> A
    assert "A" in artifacts_dir.visible_producer_node_ids("C")
    assert "A" in ctx_store.visible_producer_node_ids("C")

    artifacts_dir.publish("A", "k", 1)
    assert artifacts_dir.get("C", "A", "k") == 1


def test_workflow_ctx_ref_visibility_error_has_diagnostic_path() -> None:
    node_a = WorkflowNodeIr(node_id="A", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=())
    node_d = WorkflowNodeIr(
        node_id="D",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=3,
        deps=(),
        init_vars={"x": {"$ctx": {"node": "A", "key": "k"}}},
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, node_d),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    ctx_store = WorkflowCtxStore(workflow_ir)

    # `_validate_workflow_ctx_refs` is internal SSOT used by runtime.
    from scalim.workflow import execute as workflow_execute  # noqa: PLC0415

    with pytest.raises(ScalimWorkflowConfigError) as excinfo:
        workflow_execute._validate_workflow_ctx_refs(workflow_ir, ctx_store=ctx_store)  # noqa: SLF001

    assert excinfo.value.path == "workflow.runs.3.init_vars.x"
