import argparse
import json
from pathlib import Path

import scalim_cli.yaml_dsl as yaml_dsl_cli


def _write_minimal_demand_yaml(path: Path, *, name: str) -> None:
    path.write_text(
        (
            """
name: {name}

main_source:
  source_id: main
  loader: "no_such_module:load_main"
  params:
    start_time: {{$init_var: start_time}}
  fields:
    id: {{extract: id}}
""".format(name=str(name))
        ).lstrip(),
        encoding="utf-8",
    )


def test_yaml_dsl_viz_compile_demand_exports_static_artifacts(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.demand.yaml"
    _write_minimal_demand_yaml(yaml_path, name="demo")

    out_dir = tmp_path / "viz_out"
    args = argparse.Namespace(
        viz_type="demand",
        yaml_file=yaml_path,
        output_dir=out_dir,
    )

    code = yaml_dsl_cli._run_viz_compile(args)
    assert code == 0

    snapshot_path = out_dir / "viz_snapshot.json"
    schedule_path = out_dir / "viz_schedule_plan.json"
    assert snapshot_path.exists()
    assert schedule_path.exists()

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert "nodes" in snapshot
    assert "edges" in snapshot


def test_yaml_dsl_viz_compile_workflow_exports_bundle_and_manifest(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text("", encoding="utf-8")

    demand_a = tmp_path / "a.demand.yaml"
    demand_b = tmp_path / "b.demand.yaml"
    _write_minimal_demand_yaml(demand_a, name="a")
    _write_minimal_demand_yaml(demand_b, name="b")

    wf_dir = tmp_path / "wf"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf_path = wf_dir / "demo.workflow.yaml"
    wf_path.write_text(
        (
            """
workflow:
  runs:
    - id: a
      demand: "@/a.demand.yaml"
    - id: b
      demand: "@/b.demand.yaml"
      depends_on: [a]
""".lstrip()
        ),
        encoding="utf-8",
    )

    out_root = tmp_path / "bundle_out"
    args = argparse.Namespace(
        viz_type="workflow",
        yaml_file=wf_path,
        output_dir=out_root,
    )
    code = yaml_dsl_cli._run_viz_compile(args)
    assert code == 0

    scalim_viz_dir = out_root / "scalim-viz"
    assert (scalim_viz_dir / "workflow" / "viz_snapshot.json").exists()
    assert (scalim_viz_dir / "bundle_manifest.json").exists()
    assert (scalim_viz_dir / "a" / "viz_snapshot.json").exists()
    assert (scalim_viz_dir / "a" / "viz_schedule_plan.json").exists()
    assert (scalim_viz_dir / "b" / "viz_snapshot.json").exists()
    assert (scalim_viz_dir / "b" / "viz_schedule_plan.json").exists()

    workflow_snapshot = json.loads((scalim_viz_dir / "workflow" / "viz_snapshot.json").read_text(encoding="utf-8"))
    nodes = {item.get("id"): item for item in (workflow_snapshot.get("nodes") or [])}
    assert nodes.get("workflow_node:a", {}).get("data", {}).get("demand_run_id") == "a"
    assert nodes.get("workflow_node:b", {}).get("data", {}).get("demand_run_id") == "b"

    manifest = json.loads((scalim_viz_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("version") == 1
    runs = {item.get("id"): item for item in (manifest.get("runs") or [])}
    assert "workflow" in runs
    assert "a" in runs
    assert "b" in runs
