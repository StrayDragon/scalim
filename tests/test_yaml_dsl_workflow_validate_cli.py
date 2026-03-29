import argparse
import json
from pathlib import Path

import scalim.cli.yaml_dsl as yaml_dsl_cli


def _workflow_args(path: Path, *, json_output: bool) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        yaml_type="workflow",
        path_aliases=[],
        json=json_output,
        verbose=False,
    )


def test_yaml_dsl_validate_workflow_fails_when_writes_is_present(tmp_path: Path, capsys) -> None:
    demand_path = tmp_path / "demand.yaml"
    demand_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
""".lstrip(),
        encoding="utf-8",
    )

    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        """
workflow:
  resources:
    csvs:
      out:
        path: ./out.csv
  runs:
    - id: r1
      demand: ./demand.yaml
      writes:
        - csv_append:
            csv: out
            output: missing_output
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl_cli._run_validate(_workflow_args(workflow_path, json_output=True))
    assert code == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "workflow-validate"
    assert payload["ok"] is False
    assert len(payload["results"]) == 1

    workflow_result = payload["results"][0]
    assert workflow_result["yaml_path"] == str(workflow_path.resolve())
    assert any(item["path"] == "workflow.runs.0.writes" for item in workflow_result["errors"])


def test_yaml_dsl_validate_workflow_fails_when_demand_has_semantic_errors(tmp_path: Path, capsys) -> None:
    demand_path = tmp_path / "demand.yaml"
    demand_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  unknown_field: 1
""".lstrip(),
        encoding="utf-8",
    )

    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        """
workflow:
  runs:
    - id: r1
      demand: ./demand.yaml
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl_cli._run_validate(_workflow_args(workflow_path, json_output=True))
    assert code == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "workflow-validate"
    assert payload["ok"] is False
    assert len(payload["results"]) == 2

    demand_result = payload["results"][1]
    assert demand_result["mode"] == "validate"
    assert demand_result["ok"] is False
    assert any(item["path"] == "main_source.unknown_field" and item.get("loc", {}).get("line") for item in demand_result["errors"])


def test_yaml_dsl_validate_workflow_json_ok_matches_exit_code(tmp_path: Path, capsys) -> None:
    demand_path = tmp_path / "demand.yaml"
    demand_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
""".lstrip(),
        encoding="utf-8",
    )

    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        """
workflow:
  runs:
    - id: r1
      demand: ./demand.yaml
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl_cli._run_validate(_workflow_args(workflow_path, json_output=True))
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert all(item["ok"] is True for item in payload["results"])
