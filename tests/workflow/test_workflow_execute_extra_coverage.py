from dataclasses import replace
from pathlib import Path

import pytest


def test_workflow_cache_pool_requires_derived_consumers_mapping() -> None:
    from scalim.spec.ir._workflow import (
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

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match="requires derived consumers mapping") as excinfo:
        _ = workflow_execute_mod._maybe_build_workflow_cache_pool(
            workflow_exec_id="wf_test",
            workflow_ir=workflow_ir,
            workflow_instrumentation=object(),  # not accessed in this branch
            logical_keys_by_node_id=None,
            consumers_by_logical_key=None,
        )
    assert excinfo.value.path == "workflow.options.cache_pool"


def test_run_workflow_ir_works_without_build_demand_run_result_fn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.dsl.yaml_dsl.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    monkeypatch.chdir(tmp_path)

    demand_yaml = tmp_path / "demand.yaml"
    demand_yaml.write_text(
        (
            """
name: demo
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: detail
    to: {file: detail_csv}
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

    base_options = RunOptions(allowed_modules=frozenset(["tests.fixtures"]))

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
    from scalim.sinks import InMemoryCsv
    from scalim.sinks.rows import InMemoryRows
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
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
    assert artifacts_dir.get_optional("p1", "p1", "missing") is None
    artifacts_dir.discard("p1", "outputs")
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p1", "p1", "outputs")

    artifacts_dir.discard_in_memory_csv_output("p0", "detail")

    artifacts_dir.publish("p2", "in_memory_csv_outputs", {"detail": InMemoryCsv(header=["id"], rows=[])})
    artifacts_dir.discard_in_memory_csv_output("p2", "detail")
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p2", "p2", "in_memory_csv_outputs")

    artifacts_dir.publish("p2b", "in_memory_csv_outputs", "nope")
    artifacts_dir.discard_in_memory_csv_output("p2b", "detail")
    assert artifacts_dir.get("p2b", "p2b", "in_memory_csv_outputs") == "nope"

    artifacts_dir.publish("p3", "in_memory_csv_outputs", {"detail": InMemoryCsv(header=["id"], rows=[])})
    artifacts_dir.discard_all_in_memory_csv_outputs()
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p3", "p3", "in_memory_csv_outputs")

    artifacts_dir.publish("p4", "in_memory_rows_outputs", {"detail": InMemoryRows(header=["id"], rows=[[1]])})
    artifacts_dir.discard_in_memory_rows_output("p4", "detail")
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p4", "p4", "in_memory_rows_outputs")

    artifacts_dir.publish("p5", "in_memory_rows_outputs", {"detail": InMemoryRows(header=["id"], rows=[[1]])})
    artifacts_dir.discard_all_in_memory_rows_outputs()
    with pytest.raises(KeyError):
        _ = artifacts_dir.get("p5", "p5", "in_memory_rows_outputs")


def test_resolve_workflow_input_csv_missing_in_memory_artifact_raises() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
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

    with pytest.raises(workflow_execute_mod.ScalimWorkflowWriteError, match="Missing workflow-managed in-memory CSV artifact"):
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            consumer_decl_order=0,
            input_node_id="a",
            input_output_id="detail",
            error_prefix="write node",
        )


def test_resolve_workflow_input_csv_invisible_input_node_id_raises_config_error() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError) as excinfo:
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="consumer",
            consumer_decl_order=1,
            input_node_id="producer",
            input_output_id="detail",
            error_prefix="write node",
        )

    assert excinfo.value.path == "workflow.runs.1.input_node_id"


def test_resolve_workflow_input_csv_in_memory_map_visibility_error_path_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    def _fake_get_optional(consumer_node_id: str, producer_node_id: str, artifact_id: str) -> object:
        if artifact_id == "outputs":
            return {"detail": ""}
        if artifact_id == "in_memory_csv_outputs":
            raise ValueError("boom")
        raise AssertionError("unexpected artifact_id={!r}".format(artifact_id))

    monkeypatch.setattr(artifacts_dir, "get_optional", _fake_get_optional)

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError) as excinfo:
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            consumer_decl_order=0,
            input_node_id="a",
            input_output_id="detail",
            error_prefix="write node",
        )

    assert excinfo.value.path == "workflow.runs.0.input_node_id"


def test_resolve_workflow_output_export_header_visibility_error_path_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    def _fake_get_optional(consumer_node_id: str, producer_node_id: str, artifact_id: str) -> object:
        _ = consumer_node_id, producer_node_id
        if artifact_id == "in_memory_csv_export_headers":
            raise ValueError("boom")
        raise AssertionError("unexpected artifact_id={!r}".format(artifact_id))

    monkeypatch.setattr(artifacts_dir, "get_optional", _fake_get_optional)

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError) as excinfo:
        _ = workflow_execute_mod._resolve_workflow_output_export_header(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            consumer_decl_order=0,
            input_node_id="a",
            input_output_id="detail",
        )

    assert excinfo.value.path == "workflow.runs.0.input_node_id"


def test_resolve_workflow_input_csv_missing_outputs_mapping_and_unknown_and_non_csv() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    with pytest.raises(workflow_execute_mod.ScalimWorkflowWriteError, match="requires demand outputs mapping"):
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            consumer_decl_order=0,
            input_node_id="a",
            input_output_id="detail",
            error_prefix="write node",
        )

    artifacts_dir.publish("a", "outputs", {"detail": "./out.xlsx"})
    with pytest.raises(workflow_execute_mod.ScalimWorkflowWriteError, match="only supports CSV outputs"):
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            consumer_decl_order=0,
            input_node_id="a",
            input_output_id="detail",
            error_prefix="write node",
        )

    artifacts_dir.publish("a", "outputs", {"other": "./out.csv"})
    with pytest.raises(workflow_execute_mod.ScalimWorkflowWriteError, match="Unknown demand output id"):
        _ = workflow_execute_mod._resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id="a",
            consumer_decl_order=0,
            input_node_id="a",
            input_output_id="detail",
            error_prefix="write node",
        )


def test_run_workflow_write_and_append_nodes_workbook_and_sheetbook_branches() -> None:
    from scalim.spec.ir._workflow import (
        AppendSheetNodeIr,
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowOptionsIr,
        WorkflowNodeType,
        WriteSheetNodeIr,
    )
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    class _Recorder:
        def __init__(self) -> None:
            self.calls = []

        def apply_workbook_sheet(self, **kwargs: object) -> None:
            self.calls.append(("workbook_sheet", dict(kwargs)))

        def apply_sheetbook_sheet(self, **kwargs: object) -> None:
            self.calls.append(("sheetbook_sheet", dict(kwargs)))

        def apply_workbook_append(self, **kwargs: object) -> None:
            self.calls.append(("workbook_append", dict(kwargs)))

        def apply_sheetbook_append(self, **kwargs: object) -> None:
            self.calls.append(("sheetbook_append", dict(kwargs)))

    rec = _Recorder()

    artifacts_dir.publish("w", "outputs", {"detail": "./out.csv"})
    workbook_node = WriteSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.WRITE_SHEET,
        decl_order=0,
        deps=(),
        resource_type="workbook",
        resource_id="report",
        sheet="S",
        input_node_id="w",
        input_output_id="detail",
        on_conflict="error",
    )
    workflow_execute_mod._run_workflow_write_sheet_node(workbook_node, artifacts_dir=artifacts_dir, resource_manager=rec)  # type: ignore[arg-type]

    sheetbook_node = WriteSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.WRITE_SHEET,
        decl_order=0,
        deps=(),
        resource_type="sheetbook",
        resource_id="sb",
        sheet="S",
        input_node_id="w",
        input_output_id="detail",
        on_conflict="error",
    )
    workflow_execute_mod._run_workflow_write_sheet_node(sheetbook_node, artifacts_dir=artifacts_dir, resource_manager=rec)  # type: ignore[arg-type]

    append_workbook = AppendSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.APPEND_SHEET,
        decl_order=0,
        deps=(),
        resource_type="workbook",
        resource_id="report",
        sheet="S",
        input_node_id="w",
        input_output_id="detail",
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    workflow_execute_mod._run_workflow_append_sheet_node(append_workbook, artifacts_dir=artifacts_dir, resource_manager=rec)  # type: ignore[arg-type]

    append_sheetbook = AppendSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.APPEND_SHEET,
        decl_order=0,
        deps=(),
        resource_type="sheetbook",
        resource_id="sb",
        sheet="S",
        input_node_id="w",
        input_output_id="detail",
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    workflow_execute_mod._run_workflow_append_sheet_node(append_sheetbook, artifacts_dir=artifacts_dir, resource_manager=rec)  # type: ignore[arg-type]

    kinds = [c[0] for c in rec.calls]
    assert kinds == ["workbook_sheet", "sheetbook_sheet", "workbook_append", "sheetbook_append"]


def test_build_workflow_resource_defs_covers_workbook_sheetbook_and_book_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod

    monkeypatch.chdir(tmp_path)

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(
            WorkflowResourceIr(resource_id="report", resource_type="workbook", path="./out", options={"allow_formulas": True}),
            WorkflowResourceIr(resource_id="out", resource_type="csv", path="./out", options={}),
            WorkflowResourceIr(
                resource_id="sb",
                resource_type="sheetbook",
                path="./out",
                options={"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {"allow_formulas": False}},
            ),
        ),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    workflow_exec_id = "wf_test"
    workbook_defs, workbook_allow_formulas, csv_defs, sheetbook_defs = workflow_execute_mod._build_workflow_resource_defs(
        workflow_ir, workflow_exec_id=workflow_exec_id
    )
    assert workbook_defs["report"].endswith("/versions/{}/books/report.xlsx".format(workflow_exec_id))
    assert workbook_allow_formulas["report"] is True
    assert csv_defs["out"].endswith("/versions/{}/files/out.csv".format(workflow_exec_id))
    assert "sb" in sheetbook_defs
    assert sheetbook_defs["sb"].export_path is not None
    assert str(sheetbook_defs["sb"].export_path).endswith("/versions/{}/books/sb.xlsx".format(workflow_exec_id))

    bad_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="b0", resource_type="book", path="", options="nope"),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match="Invalid workflow resource options for book"):
        _ = workflow_execute_mod._build_workflow_resource_defs(bad_ir, workflow_exec_id=workflow_exec_id)

    bad_kind_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="b1", resource_type="book", path="", options={"kind": "nope"}),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match="Unknown book kind"):
        _ = workflow_execute_mod._build_workflow_resource_defs(bad_kind_ir, workflow_exec_id=workflow_exec_id)


def test_workflow_options_bool_returns_default_when_opts_is_not_mapping() -> None:
    from scalim.workflow import execute as workflow_execute_mod

    assert workflow_execute_mod._options_bool(None, "x", default=True) is True  # noqa: SLF001
    assert workflow_execute_mod._options_bool("nope", "x", default=False) is False  # noqa: SLF001


def test_build_workflow_resource_defs_rejects_empty_output_root_for_xlsx_file_book() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_exec_id = "wf_test"
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="report", resource_type="book", path="", options={"kind": "xlsx_file"}),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match=r"Output root must be a non-empty string") as excinfo:
        _ = workflow_execute_mod._build_workflow_resource_defs(workflow_ir, workflow_exec_id=workflow_exec_id)
    assert excinfo.value.path == "workflow.resources.books.report.path"


def test_build_workflow_resource_defs_rejects_existing_version_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod

    monkeypatch.chdir(tmp_path)
    workflow_exec_id = "wf_test"
    (tmp_path / "out" / "versions" / workflow_exec_id).mkdir(parents=True)

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="report", resource_type="workbook", path="./out", options={}),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match=r"Version directory already exists") as excinfo:
        _ = workflow_execute_mod._build_workflow_resource_defs(workflow_ir, workflow_exec_id=workflow_exec_id)
    assert excinfo.value.path == "workflow.resources.workbooks.report.path"


def test_build_workflow_resource_defs_sheetbook_can_omit_export_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod

    monkeypatch.chdir(tmp_path)
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(
            WorkflowResourceIr(
                resource_id="sb",
                resource_type="sheetbook",
                path="",
                options={
                    "budget": {"max_sheets": 1, "max_total_cells": 1},
                    "export_xlsx": {"allow_formulas": False},
                },
            ),
        ),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    _workbook_defs, _workbook_allow_formulas, _csv_defs, sheetbook_defs = workflow_execute_mod._build_workflow_resource_defs(
        workflow_ir, workflow_exec_id="wf_test"
    )
    assert sheetbook_defs["sb"].export_path is None


def test_workflow_try_submit_ready_reraises_config_error() -> None:
    import concurrent.futures

    from scalim.spec.ir._workflow import (
        WorkflowArtifactsIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )
    from scalim.hooks import HookManager
    from scalim.ob.hub import InstrumentationHub
    from scalim.ob.manager import ObserverManager
    from scalim.workflow import execute as workflow_execute_mod
    from scalim.workflow.execute_controller import WorkflowRunController

    node = WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="demand.yaml")
    workflow_ir = WorkflowIr(
        nodes=(node,),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    def _compile_demand(*_args: object, **_kwargs: object) -> object:
        raise workflow_execute_mod.ScalimWorkflowConfigError("boom", path="workflow.runs")

    workflow_instrumentation = InstrumentationHub(
        hook_manager=HookManager(),
        observer_manager=ObserverManager(run_id="wf_test"),
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match="boom"):
            controller = WorkflowRunController.build_for_prepared_run(
                executor=executor,
                workflow_exec_id="wf_test",
                workflow_ir=workflow_ir,
                artifacts_dir=artifacts_dir,
                ctx_store=object(),  # 该用例不触发 ctx 渲染
                max_concurrency=1,
                failure_policy="all_fail",
                bundle_viz_base_config=None,
                workflow_instrumentation=workflow_instrumentation,
                workflow_cache_pool=None,
                resource_manager=object(),  # 不会触发资源写入
                write_output_ids_by_run_id={},
                write_consumers_remaining_by_output_key={},
                main_rows_consumers_remaining_by_run_id={},
                captured_demand_events_by_node_id={},
                captured_demand_hook_events_by_node_id={},
                captured_demand_viz_observer_by_node_id={},
                captured_demand_request_by_node_id={},
                compile_demand_node_fn=workflow_execute_mod._compile_demand_node,
                compile_demand_fn=_compile_demand,
                build_demand_run_result_fn=None,
                run_ir_fn=workflow_execute_mod.run_ir,
                run_workflow_write_node_fn=workflow_execute_mod._run_workflow_write_node,
                capture_observability=False,
                workflow_replay_instrumentation=None,
                workflow_components=(),
            )
            controller.submit_ready_nodes()


def test_workflow_artifacts_directory_get_optional_variants() -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = workflow_execute_mod.WorkflowArtifactsDirectory(workflow_ir)

    assert artifacts_dir.get_optional("a", "a", "outputs") is None

    with pytest.raises(ValueError, match="not visible"):
        _ = artifacts_dir.get_optional("consumer", "producer", "outputs")


def test_workflow_write_consumer_counts_missing_is_best_effort(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.execution.run_ir import run_ir as real_run_ir
    from scalim.spec.ir._workflow import (
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
outputs:
  - name: detail
    to: {{file: detail_csv}}
    fields: [order_id]
resources:
  files:
    detail_csv: {{kind: csv_file, path: "{detail_path}"}}
    """
        )
        .format(detail_path=str(tmp_path / "out"))
        .lstrip(),
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
        resources=(WorkflowResourceIr(resource_id="merged", resource_type="csv", path=str(tmp_path / "out"), options=None),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "w": ()}),
    )

    base_options = RunOptions(allowed_modules=frozenset(["tests.fixtures"]))

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


def test_commit_workflow_resources_discards_on_commit_failure() -> None:
    from scalim.workflow import execute as workflow_execute_mod
    from scalim.workflow.report import WorkflowRunOutcome

    class _FailingResourceManager:
        def __init__(self) -> None:
            self.discards = []

        def discard_all(self, *, workflow_node_id: str, reason: str) -> None:
            self.discards.append((str(workflow_node_id), str(reason)))

        def commit_all(self) -> None:
            raise workflow_execute_mod.ScalimWorkflowWriteError("boom")  # noqa: SLF001

    mgr = _FailingResourceManager()

    outcomes = [WorkflowRunOutcome(run_id="a", demand_path="demand.yaml", result=None, error=None)]
    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match=r"boom"):
        workflow_execute_mod._commit_workflow_resources(  # noqa: SLF001
            resource_manager=mgr, outcomes=outcomes, failed=None
        )

    assert mgr.discards == [("__wf__discard", "resource_commit_failed")]


def test_run_workflow_ir_reraises_config_error_from_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    def _boom_commit_all(self: object) -> None:
        _ = self
        raise workflow_execute_mod.ScalimWorkflowWriteError("boom")

    monkeypatch.setattr(workflow_execute_mod.WorkflowResourceManager, "commit_all", _boom_commit_all)

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError, match=r"boom") as excinfo:
        _ = workflow_execute_mod.run_workflow_ir(
            str(tmp_path / "workflow.yaml"),
            workflow_ir,
            compile_demand_fn=lambda *_args, **_kwargs: object(),
        )

    assert excinfo.value.path == "workflow.resources"


def test_workflow_negative_write_consumer_count_is_reported(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.execution.run_ir import run_ir as real_run_ir
    from scalim.spec.ir._workflow import (
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
outputs:
  - name: detail
    to: {{file: detail_csv}}
    fields: [order_id]
resources:
  files:
    detail_csv: {{kind: csv_file, path: "{detail_path}"}}
"""
        )
        .format(detail_path=str(tmp_path / "out"))
        .lstrip(),
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
        resources=(WorkflowResourceIr(resource_id="merged", resource_type="csv", path=str(tmp_path / "out"), options=None),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "w": ()}),
    )

    base_options = RunOptions(allowed_modules=frozenset(["tests.fixtures"]))

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


def test_workflow_write_consumer_count_decrements_for_multiple_write_nodes(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl.runtime.compiler import compile as compile_demand_yaml
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.execution.run_ir import run_ir as real_run_ir
    from scalim.spec.ir._workflow import (
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
outputs:
  - name: detail
    to: {{file: detail_csv}}
    fields: [order_id]
resources:
  files:
    detail_csv: {{kind: csv_file, path: "{detail_path}"}}
"""
        )
        .format(detail_path=str(tmp_path / "out"))
        .lstrip(),
        encoding="utf-8",
    )

    workflow_ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path=str(demand_yaml)),
            AppendSheetNodeIr(
                node_id="w0",
                node_type=WorkflowNodeType.APPEND_SHEET,
                decl_order=1,
                deps=("a",),
                resource_type="csv",
                resource_id="merged0",
                sheet=None,
                input_node_id="a",
                input_output_id="detail",
                align_by="header",
                header_policy="once",
                on_mismatch="error",
            ),
            AppendSheetNodeIr(
                node_id="w1",
                node_type=WorkflowNodeType.APPEND_SHEET,
                decl_order=2,
                deps=("a",),
                resource_type="csv",
                resource_id="merged1",
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
        resources=(
            WorkflowResourceIr(resource_id="merged0", resource_type="csv", path=str(tmp_path / "out"), options=None),
            WorkflowResourceIr(resource_id="merged1", resource_type="csv", path=str(tmp_path / "out"), options=None),
        ),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "w0": (), "w1": ()}),
    )

    base_options = RunOptions(allowed_modules=frozenset(["tests.fixtures"]))

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
        prepared.write_consumers_remaining_by_output_key[("a", "detail")] = 2
        outcomes, failed, _failed_exc = workflow_execute_mod._execute_workflow_run(
            prepared,
            compile_demand_fn=_compile_demand_node,
            build_demand_run_result_fn=None,
            run_ir_fn=real_run_ir,
        )
        workflow_execute_mod._commit_workflow_resources(resource_manager=prepared.resource_manager, outcomes=outcomes, failed=failed)
        resources_finalized = True
        assert failed is None
        assert prepared.write_consumers_remaining_by_output_key.get(("a", "detail")) is None
    finally:
        workflow_execute_mod._cleanup_workflow_finally(prepared, resources_finalized=resources_finalized)
