import json
from pathlib import Path

from scalim.dsl.by_yaml import run_workflow as run_workflow_public
from scalim.dsl.by_yaml.runtime.workflow_entrypoints import run_workflow as run_workflow_runtime


def _write_demand_yaml(tmp_path: Path, *, file_name: str, name: str, output_path: Path) -> Path:
    yaml_content = """
name: {name}
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {{}}
outputs:
  - name: detail
    container: {{type: csv, path: {output_path}}}
    fields: [order_id]
""".format(
        name=str(name),
        output_path=json.dumps(str(output_path)),
    )

    p = tmp_path / str(file_name)
    p.write_text(yaml_content, encoding="utf-8")
    return p


def _write_workflow_yaml(tmp_path: Path, *, file_name: str, run_id: str, demand_file: str) -> Path:
    yaml_content = """
workflow:
  runs:
    - id: {run_id}
      demand: {demand_file}
  options:
    max_concurrency: 1
    failure_policy: all_fail
""".format(
        run_id=str(run_id),
        demand_file=str(demand_file),
    )

    p = tmp_path / str(file_name)
    p.write_text(yaml_content, encoding="utf-8")
    return p


def test_stable_workflow_entrypoints_are_importable_and_runnable(tmp_path: Path) -> None:
    wf1_dir = tmp_path / "wf1"
    wf1_dir.mkdir()
    _ = _write_demand_yaml(
        wf1_dir,
        file_name="a.yaml",
        name="a",
        output_path=wf1_dir / "a.csv",
    )
    wf1 = _write_workflow_yaml(wf1_dir, file_name="wf.yaml", run_id="a", demand_file="a.yaml")
    result1 = run_workflow_public(str(wf1), allowed_modules=frozenset(["tests"]))
    assert not result1.errors()

    wf2_dir = tmp_path / "wf2"
    wf2_dir.mkdir()
    _ = _write_demand_yaml(
        wf2_dir,
        file_name="b.yaml",
        name="b",
        output_path=wf2_dir / "b.csv",
    )
    wf2 = _write_workflow_yaml(wf2_dir, file_name="wf.yaml", run_id="b", demand_file="b.yaml")
    result2 = run_workflow_runtime(str(wf2), allowed_modules=frozenset(["tests"]))
    assert not result2.errors()
