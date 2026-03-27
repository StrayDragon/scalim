import json
from pathlib import Path
from typing import Any, Dict, List

from scalim.events import (
    WorkflowCacheAcquireEvent,
    WorkflowCacheEvictEvent,
    WorkflowCacheReleaseEvent,
    WorkflowNodeCancelledEvent,
    WorkflowNodeEndEvent,
    WorkflowNodeStartEvent,
    WorkflowResourceCommitEvent,
    WorkflowResourceCreateEvent,
    WorkflowResourceDiscardEvent,
    WorkflowResourceWriteEvent,
)
from scalim.ob.presets.viz import VizObserverConfig, WorkflowVizObserver, build_workflow_viz_graph_snapshot
from scalim.ob.presets.viz import workflow as workflow_viz_module
from scalim.spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowArtifactsIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
    WorkflowResourceIr,
    WriteSheetNodeIr,
)


def _read_events(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_workflow_viz_stage_levels_handles_cycle_and_caching() -> None:
    # a <-> b forms a cycle. Also include self-dep/empty dep to cover skip branches.
    node_a = WorkflowNodeIr(
        node_id="a",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=0,
        deps=("b", "", "a"),
        demand_path="a.yaml",
    )
    node_b = WorkflowNodeIr(
        node_id="b",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=1,
        deps=("a",),
        demand_path="b.yaml",
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, node_b),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    levels = workflow_viz_module._derive_workflow_stage_levels(workflow_ir)
    assert set(levels.keys()) == {"a", "b"}
    assert all(isinstance(v, int) for v in levels.values())


def test_build_workflow_viz_graph_snapshot_builds_nodes_edges_and_resources() -> None:
    node_missing = WorkflowNodeIr(
        node_id="",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=0,
        deps=(),
        demand_path=None,
    )
    node_b = WorkflowNodeIr(
        node_id="b",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=1,
        deps=(),
        demand_path="b.yaml",
    )
    node_a = WorkflowNodeIr(
        node_id="a",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=2,
        deps=("b", "b", ""),  # duplicate + empty dep
        demand_path="a.yaml",
    )
    dup_1 = WorkflowNodeIr(
        node_id="dup",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=3,
        deps=(),
        demand_path="dup.yaml",
    )
    dup_2 = WorkflowNodeIr(
        node_id="dup",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=4,
        deps=(),
        demand_path="dup.yaml",
    )
    write = WriteSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.WRITE_SHEET,
        decl_order=5,
        deps=("a",),
        resource_type="excel",
        resource_id="res_ok",
        sheet="Sheet1",
        input_node_id="a",
        input_output_id="out",
        on_conflict="error",
    )
    append = AppendSheetNodeIr(
        node_id="p",
        node_type=WorkflowNodeType.APPEND_SHEET,
        decl_order=6,
        deps=("w", "missing_node"),  # include unknown dep to hit edge early-return
        resource_type="excel",
        resource_id="res_missing",  # not present in resources -> writes_to edge skipped
        sheet=None,
        input_node_id="w",
        input_output_id="out",
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    res_ok = WorkflowResourceIr(resource_id="res_ok", resource_type="excel", path="/tmp/res_ok.xlsx")
    res_bad = WorkflowResourceIr(resource_id="", resource_type="excel", path="/tmp/ignored.xlsx")

    workflow_ir = WorkflowIr(
        nodes=(node_missing, node_b, node_a, dup_1, dup_2, write, append),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(res_ok, res_bad),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    snapshot = build_workflow_viz_graph_snapshot(
        workflow_ir,
        demand_run_id_by_workflow_node_id={"a": "a"},
        workflow_yaml_path="wf.yaml",
    )
    nodes = {item.get("id"): item for item in snapshot.get("nodes") or []}
    edges = snapshot.get("edges") or []

    assert "workflow_node:a" in nodes
    assert "workflow_node:b" in nodes
    assert "workflow_node:w" in nodes
    assert "workflow_node:p" in nodes
    assert "workflow_resource:excel:res_ok" in nodes

    assert nodes["workflow_node:a"]["data"]["kind"] == "workflow_demand"
    assert nodes["workflow_node:a"]["data"]["demand_run_id"] == "a"
    assert nodes["workflow_node:w"]["data"]["kind"] == "workflow_write"
    assert nodes["workflow_node:p"]["data"]["kind"] == "workflow_write"

    edge_types = {(e.get("source"), e.get("target"), e.get("type")) for e in edges}
    assert ("workflow_node:b", "workflow_node:a", "depends_on") in edge_types
    assert ("workflow_node:a", "workflow_node:w", "depends_on") in edge_types
    assert ("workflow_node:w", "workflow_node:p", "depends_on") in edge_types
    assert ("workflow_node:w", "workflow_resource:excel:res_ok", "writes_to") in edge_types
    assert ("workflow_node:p", "workflow_resource:excel:res_missing", "writes_to") not in edge_types


def test_workflow_viz_observer_disabled_branches(tmp_path: Path) -> None:
    # Disabled config: event emission is skipped, but payload parsing branches still run.
    obs = WorkflowVizObserver()
    obs._ensure_started()
    assert obs._entry_workflow_node_ref_id() == "workflow_node:__workflow__"

    obs.on_workflow_started("not a dict")
    obs.on_workflow_finished("not a dict")

    # Enabled config: cover the full emission path for all supported workflow-scope events.
    out_path = tmp_path / "viz_events.jsonl"
    config = VizObserverConfig(output_path=str(out_path), run_id="workflow")
    snapshot = {"nodes": [{"id": "workflow_node:b"}, {"id": "workflow_node:a"}], "meta": {}}
    obs = WorkflowVizObserver(config=config, snapshot=snapshot)

    obs.on_workflow_started({"workflow_id": "wf"})
    obs.on_workflow_started("not a dict")
    obs.on_workflow_finished({"status": "ok"})

    obs.on_workflow_node_start(
        WorkflowNodeStartEvent(workflow_exec_id="wf_exec", workflow_node_id="a", node_type="demand", demand_path="a.yaml")
    )
    obs.on_workflow_node_end(
        WorkflowNodeEndEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            node_type="demand",
            status="ok",
            demand_path="a.yaml",
            error_type=None,
            error_message=None,
        )
    )
    obs.on_workflow_node_cancelled(
        WorkflowNodeCancelledEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="b",
            node_type="demand",
            reason="policy_all_fail",
            message="cancelled",
            demand_path="b.yaml",
        )
    )

    obs.on_workflow_cache_acquire(
        WorkflowCacheAcquireEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            cache_kind="preload_forever",
            source_id="src",
            signature_digest="deadbeef",
            cache_status="miss",
            conflict_policy="error",
        )
    )
    obs.on_workflow_cache_release(
        WorkflowCacheReleaseEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            cache_kind="preload_forever",
            source_id="src",
            signature_digest="deadbeef",
            remaining_consumers=1,
            release_policy="dag_refcount",
            is_pinned=False,
        )
    )
    obs.on_workflow_cache_evict(
        WorkflowCacheEvictEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            cache_kind="preload_forever",
            source_id="src",
            signature_digest="deadbeef",
            reason="refcount_zero",
        )
    )

    obs.on_workflow_resource_create(
        WorkflowResourceCreateEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            resource_type="excel",
            resource_id="r1",
            path="/tmp/r1.xlsx",
        )
    )
    obs.on_workflow_resource_write(
        WorkflowResourceWriteEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            resource_type="excel",
            resource_id="r1",
            path="/tmp/r1.xlsx",
            write_kind="write_sheet",
            action="write",
        )
    )
    obs.on_workflow_resource_commit(
        WorkflowResourceCommitEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            resource_type="excel",
            resource_id="r1",
            path="/tmp/r1.xlsx",
        )
    )
    obs.on_workflow_resource_discard(
        WorkflowResourceDiscardEvent(
            workflow_exec_id="wf_exec",
            workflow_node_id="a",
            resource_type="excel",
            resource_id="r1",
            path="/tmp/r1.xlsx",
            reason="error",
        )
    )

    assert out_path.exists()
    events = _read_events(out_path)
    event_types = {evt.get("event_type") for evt in events}
    assert {
        "workflow_started",
        "workflow_finished",
        "workflow_node_started",
        "workflow_node_completed",
        "workflow_node_cancelled",
    } <= event_types
