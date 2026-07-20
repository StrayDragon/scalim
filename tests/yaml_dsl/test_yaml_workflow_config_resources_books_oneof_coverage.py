import pytest

from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError, load_workflow_config_from_mapping


def _base_workflow_mapping(*, resources: object) -> dict:
    return {
        "workflow": {
            "runs": [{"id": "a", "demand": "a.yaml"}],
            "resources": resources,
        }
    }


def test_workflow_resources_books_rejects_legacy_kind_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.books\.report\.kind was removed"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"books": {"report": {"kind": "xlsx_file"}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.books\.report\.kind was removed"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"books": {"report": {"kind": "xlsx_memory"}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"workflow\.resources\.books\.report\.kind was removed"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"books": {"report": {"kind": "nope"}}}))


def test_workflow_resources_books_rejects_removed_aliases() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"xlsx_file was removed"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"books": {"report": {"xlsx_file": []}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"xlsx_file was removed"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"books": {"report": {"xlsx_file": {"path": "./out", "write_lock": True}}}})
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"xlsx_memory was removed"):
        _ = load_workflow_config_from_mapping(_base_workflow_mapping(resources={"books": {"report": {"xlsx_memory": []}}}))

    with pytest.raises(ScalimWorkflowConfigError, match=r"xlsx_memory with export_xlsx was removed"):
        _ = load_workflow_config_from_mapping(
            _base_workflow_mapping(resources={"books": {"report": {"xlsx_memory": {"export_xlsx": {"path": "out.xlsx"}}}}})
        )
