import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

import scalim.cli.yaml_dsl as yaml_dsl_cli
from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.dsl.by_yaml.config_parsing.error_envelope import ScalimYamlValidationError


def _demand_args(path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        json=True,
        verbose=False,
    )


def _workflow_args(path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        yaml_type="workflow",
        path_aliases=[],
        json=True,
        verbose=False,
    )


def _sort_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _key(item: Dict[str, Any]) -> Any:
        loc = item.get("loc") or {}
        return (
            item.get("code") or "",
            item.get("source_path") or "",
            item.get("path") or "",
            int(loc.get("line") or 0),
            int(loc.get("column") or 0),
            item.get("message") or "",
        )

    return sorted(errors, key=_key)


def _find_demand_result(payload: Dict[str, Any], *, demand_path: Path) -> Dict[str, Any]:
    resolved = str(demand_path.resolve())
    results = payload.get("results") or []
    for item in results:
        if isinstance(item, dict) and item.get("yaml_path") == resolved:
            return item
    raise AssertionError("demand result not found for {}".format(resolved))


@pytest.mark.parametrize(
    ("demand_text",),
    [
        ("a: 1\na: 2\n",),
        ("name: [\n",),
        (
            "\n".join(
                [
                    "name: demo",
                    "main_source:",
                    "  source_id: orders",
                    "sources: {}",
                    "",
                ]
            ),
        ),
    ],
)
def test_yaml_dsl_errors_match_across_cli_compile_and_workflow(tmp_path: Path, capsys, demand_text: str) -> None:
    demand_path = tmp_path / "demand.yaml"
    demand_path.write_text(demand_text, encoding="utf-8")

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

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile_yaml(str(demand_path.resolve()), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
    expected = _sort_errors([env.as_dict() for env in excinfo.value.errors])

    assert yaml_dsl_cli._run_validate(_demand_args(demand_path)) == 1
    demand_payload = json.loads(capsys.readouterr().out)
    assert _sort_errors(demand_payload["errors"]) == expected

    assert yaml_dsl_cli._run_validate(_workflow_args(workflow_path)) == 1
    workflow_payload = json.loads(capsys.readouterr().out)
    demand_result = _find_demand_result(workflow_payload, demand_path=demand_path)
    assert _sort_errors(demand_result["errors"]) == expected
