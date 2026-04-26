"""`scalim-cli yaml-dsl` 子命令烟雾测试."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

import scalim_cli.main as cli_main


def _run_cli(*args: str) -> int:
    return cli_main.main(list(args))


def test_yaml_dsl_no_subcommand_shows_help() -> None:
    rc = _run_cli("yaml-dsl")
    assert rc == 2


def test_yaml_dsl_validate_missing_file() -> None:
    with pytest.raises(SystemExit):
        _run_cli("yaml-dsl", "validate", "--nonexistent-flag")


def test_yaml_dsl_schema_path_prints_path(capsys: Any) -> None:
    rc = _run_cli("yaml-dsl", "schema", "path")
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip().endswith(".json")


def test_yaml_dsl_validate_valid_demand_returns_zero() -> None:
    demand_yaml = """\
name: test_demand
main_source:
  source_id: orders
  loader: __main__:load_rows
  fields:
    order_id:
      extract: order_id
      name: 订单ID
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(demand_yaml)
        f.flush()
        rc = _run_cli("yaml-dsl", "validate", f.name)
    Path(f.name).unlink(missing_ok=True)
    assert rc == 0


def test_yaml_dsl_validate_invalid_demand_returns_nonzero() -> None:
    demand_yaml = "totally_invalid_key: true\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(demand_yaml)
        f.flush()
        rc = _run_cli("yaml-dsl", "validate", f.name)
    Path(f.name).unlink(missing_ok=True)
    assert rc != 0


def test_yaml_dsl_schema_show_outputs_valid_json(capsys: Any) -> None:
    rc = _run_cli("yaml-dsl", "schema", "show")
    assert rc == 0
    captured = capsys.readouterr()
    schema = json.loads(captured.out)
    assert isinstance(schema, dict)
    assert "$schema" in schema or "type" in schema or "properties" in schema


def test_yaml_dsl_schema_validate_accepts_valid_demand() -> None:
    demand_yaml = """\
name: test_demand
main_source:
  source_id: orders
  loader: __main__:load_rows
  fields:
    order_id:
      extract: order_id
      name: 订单ID
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(demand_yaml)
        f.flush()
        try:
            rc = _run_cli("yaml-dsl", "schema", "validate", f.name)
        except SystemExit as exc:
            rc = exc.code
    Path(f.name).unlink(missing_ok=True)
    assert rc == 0
