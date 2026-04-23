import pytest

from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError, load_workflow_config_from_mapping


def _base_workflow_mapping(*, resources: object) -> dict:
    return {
        "workflow": {
            "runs": [{"id": "a", "demand": "a.yaml"}],
            "resources": resources,
        }
    }


def test_workflow_resources_files_accepts_null_mapping() -> None:
    cfg = load_workflow_config_from_mapping(
        _base_workflow_mapping(
            resources={
                "files": None,
            }
        )
    )
    assert cfg.resources.files == {}


def test_workflow_resources_files_rejects_non_mapping() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files must be a mapping"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": []}))


def test_workflow_resources_files_rejects_empty_file_id_key() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files keys must be non-empty strings"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"": {"csv_file": {"path": "./out"}}}}))


def test_workflow_resources_files_rejects_non_mapping_file_config() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv must be a mapping"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": "nope"}}))


def test_workflow_resources_files_parses_file_config_and_defaults_encoding() -> None:
    cfg = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {"csv_file": {"path": "./out"}}}}))
    assert cfg.resources.files["detail_csv"].kind == "csv_file"
    assert cfg.resources.files["detail_csv"].path == "./out"
    assert cfg.resources.files["detail_csv"].encoding


def test_workflow_resources_files_rejects_missing_kind_invalid_kind_and_missing_path() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv has unknown keys: path"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {"path": "./out"}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.kind was removed"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"files": {"detail_csv": {"kind": "csv_file", "path": "./out"}}})
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.csv_file\.path is required"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {"csv_file": {}}}}))


def test_workflow_resources_files_rejects_unknown_kind_missing_branch_and_branch_write_lock() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.kind was removed"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"files": {"detail_csv": {"kind": "nope", "csv_file": {"path": "./out"}}}})
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.csv_file is required"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.csv_file must be a mapping"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {"csv_file": []}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.csv_file\.write_lock was removed"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"files": {"detail_csv": {"csv_file": {"path": "./out", "write_lock": True}}}})
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.csv_file has unknown keys: unknown"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"files": {"detail_csv": {"csv_file": {"path": "./out", "unknown": 1}}}})
        )
