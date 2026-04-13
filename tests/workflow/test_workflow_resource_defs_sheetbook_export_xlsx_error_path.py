from pathlib import Path

import pytest


def test_build_workflow_resource_defs_sheetbook_export_xlsx_os_error_points_to_books_export_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
    from scalim.workflow import execute as workflow_execute_mod
    from scalim.workflow import resource_defs as resource_defs_mod

    monkeypatch.chdir(tmp_path)

    def _boom(_path: Path) -> object:
        raise OSError("boom")

    monkeypatch.setattr(resource_defs_mod.versioned_outputs, "ensure_output_root_layout", _boom)

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(
            WorkflowResourceIr(
                resource_id="sb",
                resource_type="sheetbook",
                path="./out",
                options={
                    "budget": {"max_sheets": 1, "max_total_cells": 1},
                    "export_xlsx": {"allow_formulas": False},
                },
            ),
        ),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(workflow_execute_mod.ScalimWorkflowConfigError) as excinfo:
        _ = workflow_execute_mod._build_workflow_resource_defs(workflow_ir, workflow_exec_id="wf_test")

    assert excinfo.value.path == "workflow.resources.books.sb.export_xlsx.path"
