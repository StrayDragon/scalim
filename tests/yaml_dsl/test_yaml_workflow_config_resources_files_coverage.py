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
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"": {"kind": "csv_file", "path": "./out"}}}))


def test_workflow_resources_files_rejects_non_mapping_file_config() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv must be a mapping"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": "nope"}}))


def test_workflow_resources_files_parses_file_config_and_defaults_encoding() -> None:
    cfg = load_workflow_config_from_mapping(
        _base_workflow_mapping(resources={"files": {"detail_csv": {"kind": "csv_file", "path": "./out"}}})
    )
    assert cfg.resources.files["detail_csv"].kind == "csv_file"
    assert cfg.resources.files["detail_csv"].path == "./out"
    assert cfg.resources.files["detail_csv"].encoding


def test_workflow_resources_files_rejects_missing_kind_invalid_kind_and_missing_path() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.kind is required"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {"path": "./out"}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.kind='json_file' is invalid"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"files": {"detail_csv": {"kind": "json_file", "path": "./out"}}})
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.files\.detail_csv\.path is required for kind=csv_file"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"files": {"detail_csv": {"kind": "csv_file"}}}))
