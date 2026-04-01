import csv
from pathlib import Path
from typing import Any, Dict

import pytest


def _base_root() -> Dict[str, Any]:
    return {
        "workflow": {
            "runs": [
                {
                    "id": "a",
                    "demand": "a.yaml",
                }
            ]
        }
    }


class _Instrumentation:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event_type: str, payload: Any, meta: Dict[str, Any] = None) -> None:  # noqa: ANN001
        self.events.append({"event_type": str(event_type), "payload": payload, "meta": dict(meta or {})})


def _read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return [list(row) for row in reader]


def test_load_workflow_config_from_mapping_output_staging_defaults_are_present() -> None:
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping

    cfg = load_workflow_config_from_mapping(_base_root())
    assert cfg.options.output_staging.dir_name == ".scalim-staging"
    assert cfg.options.output_staging.keep_on_success is False
    assert cfg.options.output_staging.keep_on_failure is True


def test_load_workflow_config_from_mapping_rejects_output_staging_key() -> None:
    from scalim.dsl.by_yaml.workflow import ScalimWorkflowConfigError, load_workflow_config_from_mapping

    root = _base_root()
    root.setdefault("workflow", {}).setdefault("options", {})["output_staging"] = {"dir_name": ".staging"}

    with pytest.raises(ScalimWorkflowConfigError, match="moved out of workflow YAML") as excinfo:
        _ = load_workflow_config_from_mapping(root)
    assert excinfo.value.path == "workflow.options.output_staging"


@pytest.mark.parametrize(
    ("raw", "exc_type", "match"),
    [
        ({}, TypeError, r"workflow_output_staging must be a WorkflowOutputStagingOptions"),
        ("x", TypeError, r"workflow_output_staging must be a WorkflowOutputStagingOptions"),
        (None, TypeError, r"workflow_output_staging must be a WorkflowOutputStagingOptions"),
    ],
)
def test_normalize_workflow_output_staging_override_rejects_wrong_type(raw: object, exc_type: type[Exception], match: str) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod

    with pytest.raises(exc_type, match=match):
        _ = workflow_compile_mod._normalize_workflow_output_staging_override(raw)  # noqa: SLF001


def test_normalize_workflow_output_staging_override_rejects_empty_dir_name() -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowOutputStagingOptions

    with pytest.raises(ValueError, match=r"workflow_output_staging\.dir_name must be a non-empty string"):
        _ = workflow_compile_mod._normalize_workflow_output_staging_override(  # noqa: SLF001
            WorkflowOutputStagingOptions(dir_name="")
        )


@pytest.mark.parametrize("dir_name", [".", "..", "a/b", "a\\\\b"])
def test_normalize_workflow_output_staging_override_rejects_unsafe_dir_name(dir_name: str) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowOutputStagingOptions

    with pytest.raises(ValueError, match=r"workflow_output_staging\.dir_name must be a simple directory name"):
        _ = workflow_compile_mod._normalize_workflow_output_staging_override(  # noqa: SLF001
            WorkflowOutputStagingOptions(dir_name=dir_name)
        )


def test_normalize_workflow_output_staging_override_rejects_non_bool_keep_on_success() -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowOutputStagingOptions

    with pytest.raises(TypeError, match=r"workflow_output_staging\.keep_on_success must be a bool"):
        _ = workflow_compile_mod._normalize_workflow_output_staging_override(  # noqa: SLF001
            WorkflowOutputStagingOptions(
                dir_name=".staging",
                keep_on_success="x",  # type: ignore[arg-type] intentional runtime boundary test
            )
        )


def test_normalize_workflow_output_staging_override_rejects_non_bool_keep_on_failure() -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowOutputStagingOptions

    with pytest.raises(TypeError, match=r"workflow_output_staging\.keep_on_failure must be a bool"):
        _ = workflow_compile_mod._normalize_workflow_output_staging_override(  # noqa: SLF001
            WorkflowOutputStagingOptions(
                dir_name=".staging",
                keep_on_failure="x",  # type: ignore[arg-type] intentional runtime boundary test
            )
        )


def test_output_staging_flows_from_runtime_to_ir_to_runtime(tmp_path: Path) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping
    from scalim.dsl.by_yaml.workflow_types import WorkflowOutputStagingOptions
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr
    from scalim.workflow import execute as workflow_execute_mod

    wf_obj = load_workflow_config_from_mapping(_base_root())
    output_staging = WorkflowOutputStagingOptions(dir_name=".staging", keep_on_success=True, keep_on_failure=False)
    options_ir = workflow_compile_mod._build_workflow_options_ir(wf_obj, workflow_output_staging=output_staging)  # noqa: SLF001
    assert options_ir.output_staging.dir_name == ".staging"
    assert options_ir.output_staging.keep_on_success is True
    assert options_ir.output_staging.keep_on_failure is False

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=options_ir,
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    prepared = workflow_execute_mod._prepare_workflow_run_ir(  # noqa: SLF001
        str(tmp_path / "workflow.yaml"),
        workflow_ir,
        components=None,
        bundle_viz_base_config=None,
        cache_pool_logical_keys_by_node_id=None,
        cache_pool_consumers_by_logical_key=None,
    )
    try:
        assert prepared.resource_manager._output_staging_dir_name == ".staging"  # noqa: SLF001
        assert prepared.resource_manager._output_staging_keep_on_success is True  # noqa: SLF001
        assert prepared.resource_manager._output_staging_keep_on_failure is False  # noqa: SLF001
    finally:
        workflow_execute_mod._cleanup_workflow_finally(prepared, resources_finalized=True)  # noqa: SLF001


def test_output_staging_publish_cleans_exec_dir_by_default(tmp_path: Path) -> None:
    from scalim.sinks import InMemoryCsv
    from scalim.workflow.resources import WorkflowResourceManager

    final_path = tmp_path / "out.csv"
    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={"merged": str(final_path)},
        sheetbook_defs={},
        output_staging_dir_name=".scalim-staging",
        output_staging_keep_on_success=False,
    )
    manager.apply_csv_append(
        workflow_node_id="a",
        decl_order=0,
        csv_id="merged",
        input_node_id="a",
        input_output_id="detail",
        input_csv=InMemoryCsv(header=["id"], rows=[["1"], ["2"]]),
        header_policy="once",
        on_mismatch="error",
    )
    manager.commit_all()

    assert final_path.exists()
    assert _read_csv(final_path) == [["id"], ["1"], ["2"]]

    staging_exec_dir = tmp_path / ".scalim-staging" / "wf"
    assert not staging_exec_dir.exists()


def test_output_staging_keep_on_success_preserves_staged_file(tmp_path: Path) -> None:
    from scalim.sinks import InMemoryCsv
    from scalim.workflow.resources import WorkflowResourceManager

    final_path = tmp_path / "out.csv"
    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={"merged": str(final_path)},
        sheetbook_defs={},
        output_staging_dir_name=".scalim-staging",
        output_staging_keep_on_success=True,
    )
    manager.apply_csv_append(
        workflow_node_id="a",
        decl_order=0,
        csv_id="merged",
        input_node_id="a",
        input_output_id="detail",
        input_csv=InMemoryCsv(header=["id"], rows=[["1"]]),
        header_policy="once",
        on_mismatch="error",
    )
    manager.commit_all()

    assert final_path.exists()
    staging_path = tmp_path / ".scalim-staging" / "wf" / "out.csv"
    assert staging_path.exists()


def test_output_staging_keep_on_failure_false_cleans_staged_output_on_discard(tmp_path: Path) -> None:
    from scalim.workflow.resources import WorkflowResourceManager

    final_path = tmp_path / "out.csv"
    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={},
        output_staging_dir_name=".scalim-staging",
        output_staging_keep_on_failure=False,
    )
    staging_path = Path(manager._staging_path_for_final_output(str(final_path)))  # noqa: SLF001
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.write_text("x", encoding="utf-8")
    manager._register_staged_output(  # noqa: SLF001
        resource_type="csv",
        resource_id="merged",
        workflow_node_id="a",
        staged_path=str(staging_path),
        final_path=str(final_path),
    )
    manager.discard_all(workflow_node_id="a", reason="failed")

    assert not staging_path.exists()
    assert not staging_path.parent.exists()


@pytest.mark.parametrize(
    ("dir_name", "match"),
    [
        ("", "output_staging_dir_name must be a non-empty string"),
        (".", "output_staging_dir_name must be a simple directory name"),
        ("a/b", "output_staging_dir_name must be a simple directory name"),
        ("a\\\\b", "output_staging_dir_name must be a simple directory name"),
    ],
)
def test_output_staging_runtime_rejects_invalid_dir_name(dir_name: str, match: str) -> None:
    from scalim.workflow.resources import WorkflowResourceManager

    with pytest.raises(ValueError, match=match):
        _ = WorkflowResourceManager(
            workflow_exec_id="wf",
            instrumentation=_Instrumentation(),
            workbook_defs={},
            csv_defs={},
            sheetbook_defs={},
            output_staging_dir_name=dir_name,
        )


def test_output_staging_rejects_empty_final_path(tmp_path: Path) -> None:
    from scalim.workflow.resources import WorkflowResourceManager

    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={},
    )

    with pytest.raises(ValueError, match="final_path must be a non-empty string"):
        _ = manager._staging_path_for_final_output("")  # noqa: SLF001


def test_output_staging_copy_file_atomic_cleans_temp_on_replace_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.workflow.resources import WorkflowResourceManager

    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={},
    )

    src_path = tmp_path / "src.bin"
    src_path.write_bytes(b"hello")
    final_path = tmp_path / "out.bin"

    def _raise_replace(self: Path, target: object) -> Path:  # noqa: ANN401
        _ = (self, target)
        raise RuntimeError("boom")

    monkeypatch.setattr(Path, "replace", _raise_replace)

    with pytest.raises(RuntimeError, match="boom"):
        manager._copy_file_atomic(str(src_path), final_path=str(final_path))  # noqa: SLF001

    assert list(tmp_path.glob("*.publish.tmp")) == []


def test_output_staging_publish_missing_staged_file_raises(tmp_path: Path) -> None:
    from scalim.workflow.resources import WorkflowResourceManager

    final_path = tmp_path / "out.csv"
    staged_path = tmp_path / ".scalim-staging" / "wf" / "out.csv"

    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={},
    )
    manager._register_staged_output(  # noqa: SLF001
        resource_type="csv",
        resource_id="merged",
        workflow_node_id="a",
        staged_path=str(staged_path),
        final_path=str(final_path),
    )

    with pytest.raises(Exception, match="Missing staged output for publish"):
        manager.commit_all()
