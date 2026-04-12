from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import FileResourceOverride, OutputOverride, OutputToOverride, ResourcesOverride
from scalim.dsl.yaml_dsl import workflow_compile as workflow_compile_mod
from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError, WorkflowConfig, WorkflowOptions, WorkflowRun
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    DemandConfig,
    FileConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)


def test_workflow_compile_apply_file_patch_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"p contains unknown keys"):
        _ = workflow_compile_mod._apply_file_patch(None, {"nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.kind must be a non-empty string"):
        _ = workflow_compile_mod._apply_file_patch(None, {"kind": ""}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.kind='json_file' is invalid"):
        _ = workflow_compile_mod._apply_file_patch(None, {"kind": "json_file"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.path is required for kind=csv_file"):
        _ = workflow_compile_mod._apply_file_patch(None, {"kind": "csv_file"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.encoding must be a string"):
        _ = workflow_compile_mod._apply_file_patch(FileConfig(kind="csv_file", path="a"), {"encoding": 1}, path="p")  # noqa: SLF001

    patched = workflow_compile_mod._apply_file_patch(None, {"kind": "csv_file", "path": "a", "encoding": None}, path="p")  # noqa: SLF001
    assert patched.encoding

    patched2 = workflow_compile_mod._apply_file_patch(None, {"kind": "csv_file", "path": "a", "encoding": " latin1 "}, path="p")  # noqa: SLF001
    assert patched2.encoding == "latin1"


def test_workflow_compile_resources_files_kind_mismatch_between_workflow_and_demand() -> None:
    wf = WorkflowConfig(
        runs=(WorkflowRun(id="a", demand="a.yaml"),),
        options=WorkflowOptions(),
        resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="./out")}),
    )
    demand_cfg_by_run_id = {
        "a": DemandConfig(resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="json_file", path="./out")})),
    }
    with pytest.raises(ScalimWorkflowConfigError, match=r"File kind mismatch between workflow and demand"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf,
            workflow_base_dir=Path("."),
            demand_cfg_by_run_id=demand_cfg_by_run_id,
            demand_yaml_paths_by_run_id={"a": "a.yaml"},
            init_vars=None,
            overrides_resources=None,
        )


def test_workflow_compile_resources_files_conflicting_demand_definitions() -> None:
    wf = WorkflowConfig(
        runs=(WorkflowRun(id="a", demand="a.yaml"), WorkflowRun(id="b", demand="b.yaml")),
        options=WorkflowOptions(),
    )
    demand_cfg_by_run_id = {
        "a": DemandConfig(resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="./a")})),
        "b": DemandConfig(resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="./b")})),
    }
    with pytest.raises(ScalimWorkflowConfigError, match=r"Conflicting demand file definitions for file_id='detail_csv'"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf,
            workflow_base_dir=Path("."),
            demand_cfg_by_run_id=demand_cfg_by_run_id,
            demand_yaml_paths_by_run_id={"a": "a.yaml", "b": "b.yaml"},
            init_vars=None,
            overrides_resources=None,
        )


def test_workflow_compile_resources_files_override_can_create_new_file_resource(tmp_path: Path) -> None:
    wf = WorkflowConfig(runs=(), options=WorkflowOptions())
    resources, _books, files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf,
        workflow_base_dir=tmp_path,
        demand_cfg_by_run_id={},
        demand_yaml_paths_by_run_id={},
        init_vars=None,
        overrides_resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path="./out")}),
    )
    assert files["detail_csv"].kind == "csv_file"
    assert resources
    assert any(str(r.path).endswith("out") for r in resources)


def test_workflow_compile_resources_files_same_kind_between_workflow_and_demand_continues(tmp_path: Path) -> None:
    wf = WorkflowConfig(
        runs=(WorkflowRun(id="a", demand="a.yaml"),),
        options=WorkflowOptions(),
        resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="./out")}),
    )
    demand_cfg_by_run_id = {
        "a": DemandConfig(resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="./out")})),
    }
    resources, _books, files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf,
        workflow_base_dir=tmp_path,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        demand_yaml_paths_by_run_id={"a": "a.yaml"},
        init_vars=None,
        overrides_resources=None,
    )
    assert files["detail_csv"].kind == "csv_file"
    assert resources


def test_workflow_compile_resources_files_override_patch_must_be_mapping(tmp_path: Path) -> None:
    wf = WorkflowConfig(runs=(), options=WorkflowOptions())
    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.resources\.files\.detail_csv must be a FileResourceOverride"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf,
            workflow_base_dir=tmp_path,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=ResourcesOverride(files={"detail_csv": "nope"}),  # type: ignore[arg-type]
        )


def test_workflow_compile_resources_files_invalid_kind_is_wrapped(tmp_path: Path) -> None:
    wf = WorkflowConfig(
        runs=(),
        options=WorkflowOptions(),
        resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="json_file", path="./out")}),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"Unknown file kind 'json_file'"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf,
            workflow_base_dir=tmp_path,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=None,
        )


def test_workflow_compile_effective_outputs_rejects_file_and_book_destination() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"declare only one destination"):
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
            DemandConfig(),
            overrides_outputs=[
                OutputOverride(
                    name="detail",
                    fields=("a",),
                    to=OutputToOverride(file="detail_csv", book="report"),
                )
            ],
            default_book_id=None,
        )


def test_workflow_compile_append_write_nodes_requires_file_resource_id() -> None:
    wf = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), options=WorkflowOptions())
    cfg = DemandConfig(outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(file="detail_csv"), fields=("a",)),))

    with pytest.raises(ScalimWorkflowConfigError, match=r"Missing file resource id 'detail_csv'"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={},
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )
