from dataclasses import replace
from pathlib import Path

import pytest


def test_workflow_cache_pool_requires_derived_consumers_mapping() -> None:
    from scalim.spec.ir.workflow import (
        WorkflowArtifactsIr,
        WorkflowCachePoolBudgetIr,
        WorkflowCachePoolIr,
        WorkflowIr,
        WorkflowOptionsIr,
    )
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(
            cache_pool=WorkflowCachePoolIr(
                conflict_policy="error",
                release_policy="dag_refcount",
                budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="fail_fast"),
            )
        ),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.WorkflowConfigError, match="requires derived consumers mapping") as excinfo:
        _ = workflow_execute_mod._maybe_build_workflow_cache_pool(
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            workflow_instrumentation=object(),  # not accessed in this branch
            logical_keys_by_node_id=None,
            consumers_by_logical_key=None,
        )
    assert excinfo.value.path == "workflow.options.cache_pool"


def test_run_workflow_ir_works_without_build_demand_run_result_fn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.dsl.by_yaml.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.by_yaml.runtime.contracts import RunOptions
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    monkeypatch.chdir(tmp_path)

    demand_yaml = tmp_path / "demand.yaml"
    demand_yaml.write_text(
        (
            """
name: demo
main_source:
  source_id: main
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: [order_id]
"""
        ).lstrip(),
        encoding="utf-8",
    )

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path=str(demand_yaml)),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )

    base_options = RunOptions(allowed_modules=frozenset(["tests"]))

    def _compile_demand(demand_path: str, **kwargs: object) -> object:
        node_init_vars = kwargs.get("node_init_vars") or {}
        options = base_options
        if node_init_vars:
            options = replace(base_options, init_vars=dict(node_init_vars))
        return compile_demand_yaml(str(demand_path), options=options)

    result = workflow_execute_mod.run_workflow_ir(
        str(tmp_path / "workflow.yaml"),
        workflow_ir,
        compile_demand_fn=_compile_demand,
    )

    assert len(result.outcomes) == 1
    assert result.outcomes[0].error is None
    assert result.outcomes[0].result is not None


def test_workflow_artifacts_directory_discard_variants() -> None:
    from scalim.sinks.sink_csv import InMemoryCsv
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    artifacts_dir.discard("p0", "outputs")

    artifacts_dir.publish("p1", "outputs", {"detail": "./out.csv"})
    artifacts_dir.discard("p1", "outputs")
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p1", "p1", "outputs")

    artifacts_dir.discard_in_memory_csv_output("p0", "detail")

    artifacts_dir.publish("p2", "in_memory_csv_outputs", {"detail": InMemoryCsv(header=["id"], rows=[])})
    artifacts_dir.discard_in_memory_csv_output("p2", "detail")
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p2", "p2", "in_memory_csv_outputs")

    artifacts_dir.publish("p3", "in_memory_csv_outputs", {"detail": InMemoryCsv(header=["id"], rows=[])})
    artifacts_dir.discard_all_in_memory_csv_outputs()
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p3", "p3", "in_memory_csv_outputs")


def test_resolve_workflow_input_csv_missing_in_memory_artifact_raises() -> None:
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)
    artifacts_dir.publish("a", "outputs", {"detail": ""})

    with pytest.raises(workflow_execute_mod.WorkflowWriteError, match="Missing workflow-managed in-memory CSV artifact"):
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            input_node_id="a",
            input_output_id="detail",
            error_prefix="write node",
        )


def test_workflow_write_consumer_counts_missing_is_best_effort(tmp_path: Path) -> None:
    from scalim.dsl.by_yaml.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.by_yaml.runtime.contracts import RunOptions
    from scalim.execution.run_ir import run_ir as real_run_ir
    from scalim.spec.ir.workflow import (
        AppendSheetNodeIr,
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
        WorkflowResourceIr,
    )
    from scalim.workflow import execute as workflow_execute_mod

    demand_yaml = tmp_path / "demand.yaml"
    demand_yaml.write_text(
        (
            """
name: demo
main_source:
  source_id: main
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ""}
    fields: [order_id]
"""
        ).lstrip(),
        encoding="utf-8",
    )

    workflow_ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path=str(demand_yaml)),
            AppendSheetNodeIr(
                node_id="w",
                node_type=WorkflowNodeType.APPEND_SHEET,
                decl_order=1,
                deps=("a",),
                resource_type="csv",
                resource_id="merged",
                sheet=None,
                input_node_id="a",
                input_output_id="detail",
                align_by="header",
                header_policy="once",
                on_mismatch="error",
            ),
        ),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="merged", resource_type="csv", path=str(tmp_path / "merged.csv"), options=None),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "w": ()}),
    )

    base_options = RunOptions(allowed_modules=frozenset(["tests"]))

    def _compile_demand_node(demand_path: str, **kwargs: object) -> object:
        node_init_vars = kwargs.get("node_init_vars") or {}
        managed_output_ids = kwargs.get("managed_output_ids")
        node_options = base_options
        if node_init_vars:
            node_options = replace(base_options, init_vars=dict(node_init_vars))
        if managed_output_ids:
            node_options = replace(node_options, workflow_managed_output_ids=managed_output_ids)
        return compile_demand_yaml(str(demand_path), options=node_options)

    prepared = workflow_execute_mod._prepare_workflow_run_ir(
        str(tmp_path / "workflow.yaml"),
        workflow_ir,
        components=None,
        bundle_viz_base_config=None,
        cache_pool_logical_keys_by_node_id=None,
        cache_pool_consumers_by_logical_key=None,
    )

    resources_finalized = False
    try:
        prepared.write_consumers_remaining_by_output_key.clear()
        outcomes, failed, _failed_exc = workflow_execute_mod._execute_workflow_run(
            prepared,
            compile_demand_fn=_compile_demand_node,
            build_demand_run_result_fn=None,
            run_ir_fn=real_run_ir,
        )
        workflow_execute_mod._commit_workflow_resources(resource_manager=prepared.resource_manager, outcomes=outcomes, failed=failed)
        resources_finalized = True
        assert failed is None
    finally:
        workflow_execute_mod._cleanup_workflow_finally(prepared, resources_finalized=resources_finalized)


def test_workflow_negative_write_consumer_count_is_reported(tmp_path: Path) -> None:
    from scalim.dsl.by_yaml.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.by_yaml.runtime.contracts import RunOptions
    from scalim.execution.run_ir import run_ir as real_run_ir
    from scalim.spec.ir.workflow import (
        AppendSheetNodeIr,
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
        WorkflowResourceIr,
    )
    from scalim.workflow import execute as workflow_execute_mod

    demand_yaml = tmp_path / "demand.yaml"
    demand_yaml.write_text(
        (
            """
name: demo
main_source:
  source_id: main
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ""}
    fields: [order_id]
"""
        ).lstrip(),
        encoding="utf-8",
    )

    workflow_ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path=str(demand_yaml)),
            AppendSheetNodeIr(
                node_id="w",
                node_type=WorkflowNodeType.APPEND_SHEET,
                decl_order=1,
                deps=("a",),
                resource_type="csv",
                resource_id="merged",
                sheet=None,
                input_node_id="a",
                input_output_id="detail",
                align_by="header",
                header_policy="once",
                on_mismatch="error",
            ),
        ),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="merged", resource_type="csv", path=str(tmp_path / "merged.csv"), options=None),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "w": ()}),
    )

    base_options = RunOptions(allowed_modules=frozenset(["tests"]))

    def _compile_demand_node(demand_path: str, **kwargs: object) -> object:
        node_init_vars = kwargs.get("node_init_vars") or {}
        managed_output_ids = kwargs.get("managed_output_ids")
        node_options = base_options
        if node_init_vars:
            node_options = replace(base_options, init_vars=dict(node_init_vars))
        if managed_output_ids:
            node_options = replace(node_options, workflow_managed_output_ids=managed_output_ids)
        return compile_demand_yaml(str(demand_path), options=node_options)

    prepared = workflow_execute_mod._prepare_workflow_run_ir(
        str(tmp_path / "workflow.yaml"),
        workflow_ir,
        components=None,
        bundle_viz_base_config=None,
        cache_pool_logical_keys_by_node_id=None,
        cache_pool_consumers_by_logical_key=None,
    )

    resources_finalized = False
    try:
        prepared.write_consumers_remaining_by_output_key[("a", "detail")] = 0
        outcomes, failed, failed_exc = workflow_execute_mod._execute_workflow_run(
            prepared,
            compile_demand_fn=_compile_demand_node,
            build_demand_run_result_fn=None,
            run_ir_fn=real_run_ir,
        )
        workflow_execute_mod._commit_workflow_resources(resource_manager=prepared.resource_manager, outcomes=outcomes, failed=failed)
        resources_finalized = True
        assert failed is not None
        assert isinstance(failed_exc, RuntimeError)
        assert "negative write consumer count" in str(failed_exc)
    finally:
        workflow_execute_mod._cleanup_workflow_finally(prepared, resources_finalized=resources_finalized)
