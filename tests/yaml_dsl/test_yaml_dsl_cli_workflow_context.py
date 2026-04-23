import argparse
import json
import textwrap
from pathlib import Path

import pytest

import scalim_cli.yaml_dsl as yaml_dsl_cli


def _write_yaml(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _schema_args(demand_path: Path, *, workflow: Path = None) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=demand_path,
        schema=None,
        json=True,
        verbose=False,
        workflow=workflow,
    )


def _validate_args(demand_path: Path, *, workflow: Path = None) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=demand_path,
        schema=None,
        json=True,
        verbose=False,
        yaml_type="demand",
        allowed_yaml_roots=None,
        path_aliases=[],
        workflow=workflow,
    )


def test_cli_schema_validate_and_validate_accept_workflow_context_for_outputs_bindings(tmp_path: Path, capsys) -> None:
    demand_path = tmp_path / "demand.yaml"
    _write_yaml(
        demand_path,
        """
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          fields:
            order_id: {extract: order_id}
        sources: {}
        outputs:
          - name: book_out
            to: {book: report}
            fields: [order_id]
          - name: file_out
            to: {file: detail_csv}
            fields: [order_id]
        """,
    )

    workflow_path = tmp_path / "workflow.yaml"
    _write_yaml(
        workflow_path,
        """
        workflow:
          resources:
            books:
              report:
                xlsx_file:
                  path: ./out
            files:
              detail_csv:
                csv_file:
                  path: ./out
          runs:
            - id: r1
              demand: ./demand.yaml
        """,
    )

    assert yaml_dsl_cli._run_schema_validate(_schema_args(demand_path, workflow=workflow_path)) == 0
    schema_payload = json.loads(capsys.readouterr().out)
    assert schema_payload["ok"] is True

    assert yaml_dsl_cli._run_validate(_validate_args(demand_path, workflow=workflow_path)) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is True

    assert yaml_dsl_cli._run_schema_validate(_schema_args(demand_path)) == 1
    schema_payload = json.loads(capsys.readouterr().out)
    assert schema_payload["ok"] is False
    paths = {item.get("path") for item in schema_payload.get("errors") or []}
    assert "outputs.0.to.book" in paths
    assert "outputs.1.to.file" in paths

    assert yaml_dsl_cli._run_validate(_validate_args(demand_path)) == 1
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is False
    paths = {item.get("path") for item in validate_payload.get("errors") or []}
    assert "outputs.0.to.book" in paths
    assert "outputs.1.to.file" in paths


def test_cli_schema_validate_and_validate_do_not_require_to_book_for_to_file_outputs(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "demand.yaml"
    _write_yaml(
        yaml_path,
        """
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          fields:
            order_id: {extract: order_id}
        sources: {}
        resources:
          files:
            detail_csv: {csv_file: {path: ./out}}
        outputs:
          - name: detail
            to: {file: detail_csv}
            fields: [order_id]
        """,
    )

    assert yaml_dsl_cli._run_schema_validate(_schema_args(yaml_path)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert not any("Missing outputs to.book" in item.get("message", "") for item in payload.get("errors") or [])

    assert yaml_dsl_cli._run_validate(_validate_args(yaml_path)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


@pytest.mark.parametrize("mode", ["schema", "validate"])
def test_cli_fails_fast_when_workflow_context_missing(tmp_path: Path, capsys, mode: str) -> None:
    demand_path = tmp_path / "demand.yaml"
    _write_yaml(
        demand_path,
        """
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          fields:
            order_id: {extract: order_id}
        sources: {}
        outputs:
          - name: book_out
            to: {book: report}
            fields: [order_id]
        """,
    )

    missing_workflow = tmp_path / "missing.yaml"
    args = (
        _schema_args(demand_path, workflow=missing_workflow) if mode == "schema" else _validate_args(demand_path, workflow=missing_workflow)
    )
    fn = yaml_dsl_cli._run_schema_validate if mode == "schema" else yaml_dsl_cli._run_validate

    assert fn(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any(item.get("code") == "yaml_file_not_found" for item in payload.get("errors") or [])


@pytest.mark.parametrize("mode", ["schema", "validate"])
def test_cli_fails_fast_when_workflow_context_is_not_parseable(tmp_path: Path, capsys, mode: str) -> None:
    demand_path = tmp_path / "demand.yaml"
    _write_yaml(
        demand_path,
        """
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          fields:
            order_id: {extract: order_id}
        sources: {}
        outputs:
          - name: book_out
            to: {book: report}
            fields: [order_id]
        """,
    )

    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("workflow: [\n", encoding="utf-8")

    args = _schema_args(demand_path, workflow=workflow_path) if mode == "schema" else _validate_args(demand_path, workflow=workflow_path)
    fn = yaml_dsl_cli._run_schema_validate if mode == "schema" else yaml_dsl_cli._run_validate

    assert fn(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any(item.get("code") == "yaml_parse_error" for item in payload.get("errors") or [])


@pytest.mark.parametrize("mode", ["schema", "validate"])
def test_cli_rejects_unknown_ids_even_with_workflow_context(tmp_path: Path, capsys, mode: str) -> None:
    demand_path = tmp_path / "demand.yaml"
    _write_yaml(
        demand_path,
        """
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          fields:
            order_id: {extract: order_id}
        sources: {}
        outputs:
          - name: book_out
            to: {book: missing_book}
            fields: [order_id]
          - name: file_out
            to: {file: missing_file}
            fields: [order_id]
        """,
    )

    workflow_path = tmp_path / "workflow.yaml"
    _write_yaml(
        workflow_path,
        """
        workflow:
          resources:
            books:
              report:
                xlsx_file:
                  path: ./out
            files:
              detail_csv:
                csv_file:
                  path: ./out
          runs:
            - id: r1
              demand: ./demand.yaml
        """,
    )

    args = _schema_args(demand_path, workflow=workflow_path) if mode == "schema" else _validate_args(demand_path, workflow=workflow_path)
    fn = yaml_dsl_cli._run_schema_validate if mode == "schema" else yaml_dsl_cli._run_validate

    assert fn(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    paths = {item.get("path") for item in payload.get("errors") or []}
    assert "outputs.0.to.book" in paths
    assert "outputs.1.to.file" in paths
