from argparse import Namespace
from pathlib import Path

from scalim.cli import yaml_dsl as cli_mod


def _write_simple_demand_yaml(path: Path, *, output_path: Path, file_id: str = "out_csv") -> None:
    path.write_text(
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.yaml_outputs_e2e:demo_orders_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  files:
    %s: {kind: csv_file, path: "%s"}
outputs:
  - name: detail
    to: {file: %s}
    fields: [order_id]
"""
            % (str(file_id), str(output_path), str(file_id))
        ).lstrip(),
        encoding="utf-8",
    )


def test_yaml_dsl_cli_run_writes_file_output(tmp_path: Path) -> None:
    out_path = tmp_path / "out.csv"
    demand = tmp_path / "demand.yaml"
    _write_simple_demand_yaml(demand, output_path=out_path)

    args = Namespace(
        yaml_file=demand,
        init_vars_json=None,
        template_vars_json=None,
        allowed_modules=["tests.fixtures"],
        allowed_functions=[],
        allowed_yaml_roots=[],
        template_sandbox=None,
        parallel_mode=None,
        max_workers=None,
    )
    code = cli_mod._run_run(args)  # type: ignore[attr-defined]
    assert code == 0
    assert out_path.exists()


def test_yaml_dsl_cli_run_missing_allowlist_fails_fast(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "out.csv"
    demand = tmp_path / "demand.yaml"
    _write_simple_demand_yaml(demand, output_path=out_path)

    args = Namespace(
        yaml_file=demand,
        init_vars_json=None,
        template_vars_json=None,
        allowed_modules=[],
        allowed_functions=[],
        allowed_yaml_roots=[],
        template_sandbox=None,
        parallel_mode=None,
        max_workers=None,
    )
    code = cli_mod._run_run(args)  # type: ignore[attr-defined]
    assert code == 1

    captured = capsys.readouterr()
    assert "缺少 allowlist" in captured.err
    assert "yaml_dsl.runner.allowed_modules" in captured.err


def test_yaml_dsl_cli_run_uses_scalim_yaml_runner_defaults(tmp_path: Path) -> None:
    scalim_yaml = tmp_path / "scalim.yaml"
    scalim_yaml.write_text(
        """
yaml_dsl:
  runner:
    allowed_modules:
      - tests.fixtures
""".lstrip(),
        encoding="utf-8",
    )

    out_path = tmp_path / "out.csv"
    demand = tmp_path / "demand.yaml"
    _write_simple_demand_yaml(demand, output_path=out_path)

    args = Namespace(
        yaml_file=demand,
        init_vars_json=None,
        template_vars_json=None,
        allowed_modules=[],
        allowed_functions=[],
        allowed_yaml_roots=[],
        template_sandbox=None,
        parallel_mode=None,
        max_workers=None,
    )
    code = cli_mod._run_run(args)  # type: ignore[attr-defined]
    assert code == 0
    assert out_path.exists()


def test_yaml_dsl_cli_workflow_run_executes_all_nodes(tmp_path: Path) -> None:
    out_a = tmp_path / "a.csv"
    out_b = tmp_path / "b.csv"
    demand_a = tmp_path / "a.yaml"
    demand_b = tmp_path / "b.yaml"
    _write_simple_demand_yaml(demand_a, output_path=out_a, file_id="a_csv")
    _write_simple_demand_yaml(demand_b, output_path=out_b, file_id="b_csv")

    workflow = tmp_path / "workflow.yaml"
    workflow.write_text(
        """
workflow:
  runs:
    - id: a
      demand: ./a.yaml
    - id: b
      demand: ./b.yaml
""".lstrip(),
        encoding="utf-8",
    )

    args = Namespace(
        yaml_file=workflow,
        init_vars_json=None,
        template_vars_json=None,
        allowed_modules=["tests.fixtures"],
        allowed_functions=[],
        allowed_yaml_roots=[],
        template_sandbox=None,
        parallel_mode=None,
        max_workers=None,
        path_aliases=[],
    )
    code = cli_mod._run_workflow_run(args)  # type: ignore[attr-defined]
    assert code == 0
    assert out_a.exists()
    assert out_b.exists()
