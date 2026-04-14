import json

import pytest


def test_workflow_config_error_is_single_canonical_type() -> None:
    from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError as FromDslWorkflow
    from scalim.dsl.yaml_dsl.workflow_types import ScalimWorkflowConfigError as FromDslTypes
    from scalim.workflow.errors import ScalimWorkflowConfigError as FromWorkflow

    assert FromWorkflow is FromDslWorkflow
    assert FromWorkflow is FromDslTypes


def test_workflow_config_error_message_is_consistent_across_entrypoints() -> None:
    from scalim.dsl.yaml_dsl.workflow_config import load_workflow_config_from_mapping, validate_workflow_yaml_text_json
    from scalim.workflow.errors import ScalimWorkflowConfigError

    root = {"name": "demo"}
    with pytest.raises(ScalimWorkflowConfigError) as excinfo:
        _ = load_workflow_config_from_mapping(root)  # type: ignore[arg-type]

    expected = str(excinfo.value)

    payload = json.loads(validate_workflow_yaml_text_json("name: demo\n"))
    assert payload["ok"] is False
    assert payload["errors"][0]["message"] == expected


def test_workflow_config_error_message_is_consistent_in_cli_validate(tmp_path, capsys) -> None:
    from argparse import Namespace

    from scalim_cli import yaml_dsl as cli_mod
    from scalim.dsl.yaml_dsl.workflow_config import load_workflow_config_from_mapping
    from scalim.workflow.errors import ScalimWorkflowConfigError

    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text("name: demo\n", encoding="utf-8")

    with pytest.raises(ScalimWorkflowConfigError) as excinfo:
        _ = load_workflow_config_from_mapping({"name": "demo"})  # type: ignore[arg-type]

    args = Namespace(
        yaml_file=wf_path,
        schema=None,
        json=True,
        verbose=False,
        yaml_type="workflow",
        path_aliases=[],
        allowed_yaml_roots=[],
    )
    code = cli_mod._run_validate(args)  # type: ignore[attr-defined]
    assert code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    workflow_errors = payload["results"][0]["errors"]
    assert workflow_errors[0]["message"] == str(excinfo.value)
