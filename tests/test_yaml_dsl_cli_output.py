import argparse
import json
import logging
import re
from pathlib import Path

import scalim.cli.yaml_dsl as yaml_dsl


def _write_yaml(path: Path) -> None:
    path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
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
        strict=False,
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
    assert payload["errors"][0]["line"] == 8


def test_yaml_dsl_validate_order_by_error(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "order_by.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
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


def test_yaml_dsl_validate_reports_call_by_error(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "call_by.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.call_by_fns:dummy_main_loader
  fields:
    a:
      extract: a
sources: {}
fields:
  text:
    call_by: "tests.call_by_fns:echo(true)"
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
  loader: tests.conftest.mock_loader
sources: {}
fields:
  profit:
    compute: "1"
    commpute: "2"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_validate(_args(yaml_path, json_output=False))
    assert code == 0

    out = capsys.readouterr().out
    assert "WARN" in out
    assert "Unknown field" in out
    assert "commpute" in out
    assert "help: compute" in out


def test_yaml_dsl_validate_does_not_emit_schema_validation_error_for_output_fields_string_item(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "invalid_output_fields.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
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
    assert code == 0

    out = capsys.readouterr().out
    assert "Schema validation error" not in out
    assert "OK" in out


def test_yaml_dsl_validate_does_not_log_jsonschema_skip_noise(tmp_path, caplog) -> None:
    caplog.set_level(logging.WARNING, logger="scalim.dsl.by_yaml.validator")

    yaml_path = tmp_path / "demo.yaml"
    _write_yaml(yaml_path)

    yaml_dsl._run_validate(_args(yaml_path, json_output=False))

    assert "JSONSchema is not available" not in caplog.text


def test_yaml_dsl_validate_allows_missing_sources(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "minimal.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
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
  loader: tests.conftest.mock_loader
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
