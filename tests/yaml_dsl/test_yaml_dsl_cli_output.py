import argparse
import json
import re
from pathlib import Path

import scalim.cli.yaml_dsl as yaml_dsl
import scalim.dsl.by_yaml._internal.config_parsing.validator as validator_mod


def _write_yaml(path: Path) -> None:
    path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
fields:
  profit:
    compute: order_amount - 1
""".lstrip(),
        encoding="utf-8",
    )


def _args(path: Path, *, json_output: bool) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        json=json_output,
        verbose=False,
    )


def test_yaml_dsl_validate_linter_output_has_location(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "demo.yaml"
    _write_yaml(yaml_path)

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 1

    out = capsys.readouterr().out
    assert "ERROR" in out
    pattern = r"{}:8(:\\d+)?".format(re.escape(str(yaml_path)))
    assert re.search(pattern, out)


def test_yaml_dsl_validate_json_output_has_line(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "demo.yaml"
    _write_yaml(yaml_path)

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=True))
    assert code == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"]
    assert payload["errors"][0]["loc"]["line"] == 8


def test_yaml_dsl_validate_order_by_error(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "order_by.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  order_by:
    - missing_field
  fields:
    order_id:
      extract: order_id
sources: {}
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 1

    out = capsys.readouterr().out
    assert "order_by" in out
    assert "main_source.order_by.0" in out
    assert "main_source.order_by[0]" not in out
    pattern = r"{}:6(:\\d+)?".format(re.escape(str(yaml_path)))
    assert re.search(pattern, out)


def test_yaml_dsl_validate_order_by_error_json_path_is_canonical(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "order_by.json.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  order_by:
    - missing_field
  fields:
    order_id:
      extract: order_id
sources: {}
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=True))
    assert code == 1

    payload = json.loads(capsys.readouterr().out)
    errors = payload["errors"]
    assert any(item["path"] == "main_source.order_by.0" for item in errors)
    match = next(item for item in errors if item["path"] == "main_source.order_by.0")
    assert match["loc"]["line"] == 6


def test_yaml_dsl_validate_reports_call_by_error(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "call_by.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.call_by_fns:dummy_main_loader
  fields:
    a:
      extract: a
sources: {}
fields:
  text:
    call_by: "tests.fixtures.call_by_fns:echo(true)"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 1

    out = capsys.readouterr().out
    assert "call_by" in out


def test_yaml_dsl_validate_unknown_field_renders_help(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "unknown.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
fields:
  profit:
    compute: "1"
    commpute: "2"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 1

    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "Unknown field" in out
    assert "commpute" in out
    assert "help: compute" in out


def test_yaml_dsl_validate_reports_legacy_output_as_error(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "invalid_output_fields.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - order_id
    """.lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 1

    out = capsys.readouterr().out
    assert "Legacy YAML syntax is not supported: top-level 'output'" in out
    assert "ERROR" in out


def test_yaml_dsl_validate_warns_when_jsonschema_missing_but_still_succeeds(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(validator_mod, "HAS_JSONSCHEMA", False)
    monkeypatch.setattr(validator_mod, "jsonschema", None)

    yaml_path = tmp_path / "minimal.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=True))
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["errors"] == []
    assert any("[scalim] schema:" in item["message"] and "jsonschema" in item["message"] for item in payload["warnings"])


def test_yaml_dsl_validate_still_flags_outputs_container_path_init_var_shape_errors_without_jsonschema(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.setattr(validator_mod, "HAS_JSONSCHEMA", False)
    monkeypatch.setattr(validator_mod, "jsonschema", None)

    yaml_path = tmp_path / "invalid_outputs_path.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: {$init_var: output_path, other: 1}
      unknown_field: 1
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=True))
    assert code == 1

    payload = json.loads(capsys.readouterr().out)
    errors = payload["errors"]
    paths = {item["path"] for item in errors}
    assert "resources.files.detail_csv.path" in paths
    assert "resources.files.detail_csv.unknown_field" in paths


def test_yaml_dsl_validate_allows_missing_sources(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "minimal.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 0

    out = capsys.readouterr().out
    assert "OK" in out


def test_yaml_dsl_validate_missing_sources_still_reports_unknown_source_with_path(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "unknown_source.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    customer_id:
      extract: customer_id
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 1

    out = capsys.readouterr().out
    assert "unknown source" in out
    assert "relations.orders_to_customers.steps.0" in out
