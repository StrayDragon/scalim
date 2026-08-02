import concurrent.futures
from types import SimpleNamespace

import pytest

from scalim.workflow.resource_lifecycle import WorkflowResourceLifecycle


def test_build_workflow_resource_defs_wraps_oserror_as_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod

    def _boom(_path: object) -> object:
        raise PermissionError("nope")

    from scalim.workflow import resource_defs as resource_defs_mod

    monkeypatch.setattr(resource_defs_mod.versioned_outputs, "ensure_output_root_layout", _boom)

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="detail", resource_type="csv", path="./out"),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match="Failed to prepare output root for workflow run") as excinfo:
        _ = workflow_execute_mod._build_workflow_resource_defs(workflow_ir, workflow_exec_id="wf_test")

    assert excinfo.value.path == "workflow.resources.files.detail.path"


def test_build_workflow_resource_defs_ignores_unknown_resource_type() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="weird", resource_type="weird", path="./out"),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    workbook_defs, workbook_allow_formulas_by_id, csv_defs, sheetbook_defs = workflow_execute_mod._build_workflow_resource_defs(
        workflow_ir, workflow_exec_id="wf_test"
    )

    assert workbook_defs == {}
    assert workbook_allow_formulas_by_id == {}
    assert csv_defs == {}
    assert sheetbook_defs == {}


def test_prepare_workflow_run_ir_closes_resources_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowCachePoolBudgetIr,
        WorkflowCachePoolIr,
        WorkflowIr,
        WorkflowOptionsIr,
        WorkflowResourceIr,
    )
    from scalim.workflow import execute as workflow_execute_mod

    def _boom(_path: object) -> object:
        raise PermissionError("nope")

    from scalim.workflow import resource_defs as resource_defs_mod

    monkeypatch.setattr(resource_defs_mod.versioned_outputs, "ensure_output_root_layout", _boom)

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(
            max_concurrency=1,
            failure_policy="all_fail",
            cache_pool=WorkflowCachePoolIr(
                conflict_policy="error",
                release_policy="dag_refcount",
                budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="fail_fast"),
            ),
        ),
        resources=(WorkflowResourceIr(resource_id="detail", resource_type="csv", path="./out"),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match="Failed to prepare output root for workflow run"):
        _ = workflow_execute_mod._prepare_workflow_run_ir(
            "workflow.yaml",
            workflow_ir,
            components=None,
            bundle_viz_base_config=None,
            cache_pool_logical_keys_by_node_id={},
            cache_pool_consumers_by_logical_key={},
        )


def test_prepare_workflow_run_ir_skips_cleanup_when_instrumentation_not_built() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(TypeError, match=r"Invalid component"):
        _ = workflow_execute_mod._prepare_workflow_run_ir(
            "workflow.yaml",
            workflow_ir,
            components=[object()],
            bundle_viz_base_config=None,
            cache_pool_logical_keys_by_node_id=None,
            cache_pool_consumers_by_logical_key=None,
        )


def test_run_workflow_ir_failure_carries_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod
    from scalim.workflow.report import WorkflowRunError, WorkflowRunOutcome

    failed_exc = RuntimeError("boom")
    failed_outcome = WorkflowRunOutcome(
        run_id="a",
        demand_path="demand.yaml",
        result=None,
        error=WorkflowRunError(run_id="a", demand_path="demand.yaml", exc_type="Boom", message="boom"),
    )

    class _Controller:
        def run(self) -> None:
            return

        def finalize(self) -> object:
            return [failed_outcome], failed_outcome, failed_exc

    def _fake_build_for_prepared_run(_cls: object, **_kwargs: object) -> object:
        _ = _cls
        _ = _kwargs
        return _Controller()

    monkeypatch.setattr(
        workflow_execute_mod.WorkflowRunController,
        "build_for_prepared_run",
        classmethod(_fake_build_for_prepared_run),
    )

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.ScalimWorkflowRunFailedError) as excinfo:
        _ = workflow_execute_mod.run_workflow_ir(
            "workflow.yaml",
            workflow_ir,
            compile_demand_fn=lambda *_a, **_k: object(),
        )

    assert excinfo.value.__cause__ is failed_exc


def test_run_workflow_ir_failure_without_cause_keeps_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod
    from scalim.workflow.report import WorkflowRunError, WorkflowRunOutcome

    failed_outcome = WorkflowRunOutcome(
        run_id="a",
        demand_path="demand.yaml",
        result=None,
        error=WorkflowRunError(run_id="a", demand_path="demand.yaml", exc_type="Boom", message="boom"),
    )

    class _Controller:
        def run(self) -> None:
            return

        def finalize(self) -> object:
            return [failed_outcome], failed_outcome, None

    def _fake_build_for_prepared_run(_cls: object, **_kwargs: object) -> object:
        _ = _cls
        _ = _kwargs
        return _Controller()

    monkeypatch.setattr(
        workflow_execute_mod.WorkflowRunController,
        "build_for_prepared_run",
        classmethod(_fake_build_for_prepared_run),
    )

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.ScalimWorkflowRunFailedError) as excinfo:
        _ = workflow_execute_mod.run_workflow_ir(
            "workflow.yaml",
            workflow_ir,
            compile_demand_fn=lambda *_a, **_k: object(),
        )

    assert excinfo.value.__cause__ is None


def test_workflow_controller_state_property_exposes_internal_state() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

    assert controller.state is controller._state


def test_workflow_controller_stage_barrier_helpers_handle_empty_stage_order() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
    from scalim.workflow.execute_controller import WorkflowRunController, WorkflowRunState

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail", schedule_mode="stage_barrier"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    state = WorkflowRunState(
        outcomes=[None],
        node_state={"": "ready"},
        ready_queue=[""],
        submitted={},
        remaining_prereqs={"": 0},
        prereq_failed={"": False},
        max_concurrency=1,
        failure_policy="all_fail",
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController(
            executor=executor,
            state=state,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=SimpleNamespace(),
            ctx_store=SimpleNamespace(
                visible_producer_node_ids=lambda *_a, **_k: frozenset(),
                publish_default_summary=lambda *_a, **_k: None,
            ),
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=object(),
            resource_lifecycle=SimpleNamespace(),
            write_output_ids_by_run_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

    assert controller._stage_order == []
    assert controller._current_stage() == 0
    controller._maybe_advance_stage_barrier()


def test_workflow_controller_current_stage_clamps_idx_out_of_range() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail", schedule_mode="stage_barrier"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

    controller._current_stage_idx = -1
    assert controller._current_stage() == 0
    controller._current_stage_idx = 99
    assert controller._current_stage() == 0


def test_workflow_controller_stage_barrier_returns_when_stage_members_empty_and_last() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail", schedule_mode="stage_barrier"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

    assert controller._stage_order == [0]
    controller._node_ids_by_stage[0] = frozenset()
    controller._maybe_advance_stage_barrier()
    assert controller._current_stage_idx == 0


def test_workflow_controller_stage_barrier_advances_when_stage_members_empty_and_next() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    node_a = WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml")
    node_b = WorkflowNodeIr(node_id="b", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=("a",), demand_path="b.yaml")
    workflow_ir = WorkflowIr(
        nodes=(node_a, node_b),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail", schedule_mode="stage_barrier"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

    assert controller._stage_order == [0, 1]
    controller._node_ids_by_stage[0] = frozenset()
    controller._maybe_advance_stage_barrier()
    assert controller._current_stage_idx == 1


def test_workflow_controller_stage_barrier_skips_ready_write_node_in_future_stage() -> None:
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
        WriteSheetNodeIr,
    )
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    node_a = WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml")
    node_b = WorkflowNodeIr(node_id="b", node_type=WorkflowNodeType.DEMAND, decl_order=2, deps=("a",), demand_path="b.yaml")
    write_node = WriteSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.WRITE_SHEET,
        decl_order=1,
        deps=(),
        resource_type="excel",
        resource_id="book",
        sheet="Sheet1",
        input_node_id="b",
        input_output_id="out",
        on_conflict="error",
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, write_node, node_b),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail", schedule_mode="stage_barrier"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

    assert controller.state.ready_queue == ["a", "w"]
    assert controller._pop_next_ready_write_node_id() is None
    assert controller.state.ready_queue == ["a", "w"]


def test_workflow_artifacts_directory_rejects_write_when_owner_thread_mismatch() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)
    artifacts_dir._owner_thread_id = -1

    with pytest.raises(RuntimeError, match="controller thread"):
        artifacts_dir.publish("a", "k", 1)


def test_workflow_ctx_store_rejects_write_when_owner_thread_mismatch() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow.execute import WorkflowCtxStore

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    ctx_store = WorkflowCtxStore(workflow_ir)
    ctx_store._owner_thread_id = -1

    with pytest.raises(RuntimeError, match="controller thread"):
        ctx_store.publish("a", "k", 1, path="workflow.options.ctx")


def test_workflow_controller_submit_ready_nodes_returns_when_all_fail_already_failed() -> None:
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController
    from scalim.workflow.report import WorkflowRunError, WorkflowRunOutcome

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

        controller._state.failed_outcome = WorkflowRunOutcome(
            run_id="a",
            demand_path="demand.yaml",
            result=None,
            error=WorkflowRunError(run_id="a", demand_path="demand.yaml", exc_type="Boom", message="boom"),
        )
        controller.submit_ready_nodes()

        assert controller.state.ready_queue == ["a"]


def test_workflow_controller_submit_ready_nodes_returns_when_max_concurrency_zero() -> None:
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=0, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=0,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

        controller.submit_ready_nodes()

        assert controller.state.ready_queue == ["a"]
        assert controller.state.submitted == {}


def test_workflow_controller_submit_ready_nodes_returns_when_ready_queue_contains_unknown_node_id() -> None:
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

        controller._state.ready_queue = ["missing"]
        controller.submit_ready_nodes()

        assert controller.state.ready_queue == ["missing"]
        assert controller.state.submitted == {}


def test_workflow_controller_process_completed_future_for_write_node_sets_outcome() -> None:
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
        WriteSheetNodeIr,
    )
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController

    write_node = WriteSheetNodeIr(
        node_id="w1",
        node_type=WorkflowNodeType.WRITE_SHEET,
        decl_order=0,
        deps=(),
        resource_type="book",
        resource_id="b",
        sheet="s",
        input_node_id="a",
        input_output_id="detail",
        on_conflict="error",
    )
    workflow_ir = WorkflowIr(
        nodes=(write_node,),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"w1": ()}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            _ = producer_node_id
            _ = result

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=_Ctx(),
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: object(),
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

        fut: concurrent.futures.Future[object] = concurrent.futures.Future()
        fut.set_result(None)
        controller.state.submitted[fut] = ("w1", write_node, None, None, None)

        controller.process_completed_future(fut)

        assert controller.state.outcomes[0] is not None
        assert controller.state.outcomes[0].run_id == "w1"
        assert controller.state.outcomes[0].error is None
        assert controller.state.node_state["w1"] == "done"


def test_workflow_controller_process_completed_future_capture_skips_request_when_none() -> None:
    from scalim.events import Event, EventType
    from scalim.execution.adaptive.capture import HookRecordedEvent
    from scalim.execution.contracts import ExecutionResult
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )
    from scalim.workflow.artifacts import WorkflowArtifactsDirectory
    from scalim.workflow.execute_controller import WorkflowRunController, _CapturedNodeRun

    node = WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml")
    workflow_ir = WorkflowIr(
        nodes=(node,),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)

    class _Ctx:
        def __init__(self) -> None:
            self.calls = []

        def visible_producer_node_ids(self, consumer_node_id: str) -> object:
            return frozenset([str(consumer_node_id)])

        def publish_default_summary(self, producer_node_id: str, result: object) -> None:
            self.calls.append((str(producer_node_id), getattr(result, "output_path", None)))

    ctx_store = _Ctx()

    core = ExecutionResult(
        output_path="./out",
        total_rows=0,
        duration=0.0,
        demand_ir=object(),
        plan=object(),
        outputs={},
        in_memory_csv_outputs={},
        in_memory_rows_outputs={},
        workflow_managed_output_export_headers={},
        in_memory_rows=None,
    )
    captured = _CapturedNodeRun(
        core=core,
        captured_hook_events=[
            HookRecordedEvent(
                event_type=EventType.PIPELINE_START,
                event=Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="a", payload={"x": 1}, meta={}, seq=0),
            )
        ],
        captured_events=[Event(event_type="evt", timestamp=0.0, run_id="a", payload=None, meta=None, seq=0)],
        viz_observer=None,
    )

    resource_manager = object()
    resource_lifecycle = WorkflowResourceLifecycle(resource_manager=resource_manager, artifacts_dir=artifacts_dir, cache_pool=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=ctx_store,
            max_concurrency=1,
            failure_policy="all_fail",
            bundle_viz_base_config=None,
            workflow_instrumentation=SimpleNamespace(emit=lambda *_a, **_k: None),
            workflow_cache_pool=None,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id={},
            write_consumers_remaining_by_output_key={},
            main_rows_consumers_remaining_by_run_id={},
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
            compile_demand_node_fn=lambda *_a, **_k: (object(), object()),
            compile_demand_fn=lambda *_a, **_k: object(),
            build_demand_run_result_fn=None,
            run_ir_fn=lambda *_a, **_k: core,
            run_workflow_write_node_fn=lambda *_a, **_k: None,
            capture_observability=False,
            workflow_replay_instrumentation=None,
            workflow_components=(),
        )

        fut: concurrent.futures.Future[object] = concurrent.futures.Future()
        fut.set_result(captured)
        controller.state.submitted[fut] = ("a", node, "demand.yaml", None, None)

        controller.process_completed_future(fut)

        assert "a" in controller.state.captured_demand_events_by_node_id
        assert "a" in controller.state.captured_demand_hook_events_by_node_id
        assert "a" in controller.state.captured_demand_viz_observer_by_node_id
        assert "a" not in controller.state.captured_demand_request_by_node_id
        assert ctx_store.calls == [("a", "./out")]


def test_build_demand_replay_instrumentation_allows_viz_observer_without_request() -> None:
    from scalim.ob.observer import Observer
    from scalim.workflow.execute_controller import _build_demand_replay_instrumentation

    class _DummyObserver(Observer):
        def on_event(self, event: object) -> None:
            _ = event

    out = _build_demand_replay_instrumentation(None, _DummyObserver(), workflow_components=())

    assert out is not None


def test_replay_captured_observability_replays_hook_events_without_node_replay() -> None:
    from scalim.events import Event, EventType
    from scalim.execution.adaptive.capture import HookRecordedEvent
    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )
    from scalim.workflow.execute_controller import WorkflowRunController

    class _HookManager:
        def __init__(self) -> None:
            self.emitted = []

        def emit_typed(self, event_type: str, payload: object) -> None:
            self.emitted.append((str(event_type), payload))

    replay = SimpleNamespace(hook_manager=_HookManager())
    capture = SimpleNamespace(hook_manager=object(), observer_manager=object())

    workflow_ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )

    WorkflowRunController.replay_captured_observability(
        capture_observability=True,
        workflow_replay_instrumentation=replay,
        workflow_instrumentation=capture,
        workflow_ir=workflow_ir,
        workflow_exec_id="wf_test",
        workflow_components=(),
        captured_demand_events_by_node_id={"a": []},
        captured_demand_hook_events_by_node_id={
            "a": [
                HookRecordedEvent(
                    event_type=EventType.PIPELINE_START,
                    event=Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="a", payload={"x": 1}, meta={}, seq=0),
                )
            ]
        },
        captured_demand_viz_observer_by_node_id={},
        captured_demand_request_by_node_id={},
    )

    assert len(replay.hook_manager.emitted) == 1
    assert replay.hook_manager.emitted[0][0] == EventType.PIPELINE_START.value
    assert replay.hook_manager.emitted[0][1].payload == {"x": 1}


def test_sheetbook_decide_alignment_action_returns_error_for_unknown_policy() -> None:
    from scalim.workflow import resources_sheetbook as sheetbook_mod

    assert sheetbook_mod._sheetbook_decide_alignment_action(["a"], ["b"], align_by="field_id", on_mismatch="nope") == "error"


def test_workflow_replay_event_workflow_node_id_returns_empty_for_non_dict_meta() -> None:
    from scalim.events import Event
    from scalim.workflow._internal import replay_event_classification as replay_mod

    event = Event(event_type="evt", timestamp=0.0, run_id="wf", payload=None, meta="not-a-dict", seq=0)
    assert replay_mod._workflow_event_workflow_node_id(event) == ""


def test_build_binding_signature_uses_params_none_marker() -> None:
    from scalim.spec.ir.binding import BindingIr
    from scalim.utils import relation_signature as relation_signature_mod

    sig = relation_signature_mod.build_binding_signature(BindingIr(key_field="order_id"))
    assert sig is not None
    assert sig[-1] == "params:none"
