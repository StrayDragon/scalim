import json
from pathlib import Path

from scalim.dsl.by_yaml import RunOverrides, run_workflow
from scalim.ob.presets.viz import VizObserverConfig


_ALLOWED_MODULES = frozenset(["tests.fixtures.workflow_loaders"])


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _write_minimal_demand_yaml(tmp_path: Path, *, file_name: str, name: str) -> Path:
    return _write_text(
        tmp_path / file_name,
        (
            """
name: {name}

batch_size: 1

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_main_fast"
  fields:
    ref_id: {{extract: ref_id}}
""".format(
                name=str(name)
            )
        ).lstrip(),
    )


def _write_bad_demand_yaml(tmp_path: Path, *, file_name: str, name: str) -> Path:
    # This YAML is loadable, but compilation should fail because the Python reference is invalid.
    return _write_text(
        tmp_path / file_name,
        (
            """
name: {name}

batch_size: 1

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:no_such_function"
  fields:
    ref_id: {{extract: ref_id}}
""".format(
                name=str(name)
            )
        ).lstrip(),
    )


def _write_workflow_yaml(tmp_path: Path, *, file_name: str, demand_ok: str, demand_missing: str) -> Path:
    return _write_text(
        tmp_path / file_name,
        (
            """
workflow:
  runs:
    - id: ok
      demand: {demand_ok}
    - id: bad
      demand: {demand_missing}
  options:
    max_concurrency: 1
    failure_policy: primary_only
""".format(
                demand_ok=str(demand_ok),
                demand_missing=str(demand_missing),
            )
        ).lstrip(),
    )


def test_workflow_viz_bundle_exports_linked_runs(tmp_path: Path) -> None:
    _ = _write_minimal_demand_yaml(tmp_path, file_name="ok.yaml", name="ok")
    _ = _write_bad_demand_yaml(tmp_path, file_name="bad.yaml", name="bad")
    wf = _write_workflow_yaml(tmp_path, file_name="wf.yaml", demand_ok="ok.yaml", demand_missing="bad.yaml")

    out_dir = tmp_path / "out"

    result = run_workflow(
        str(wf),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(viz_config=VizObserverConfig(output_dir=str(out_dir))),
    )

    # Workflow continues (failure_policy=primary_only), but the missing node is recorded as an error.
    assert len(result.errors()) == 1

    workflow_snapshot_path = out_dir / "scalim-viz" / "workflow" / "viz_snapshot.json"
    workflow_events_path = out_dir / "scalim-viz" / "workflow" / "viz_events.jsonl"
    ok_snapshot_path = out_dir / "scalim-viz" / "ok" / "viz_snapshot.json"
    ok_events_path = out_dir / "scalim-viz" / "ok" / "viz_events.jsonl"
    bad_snapshot_path = out_dir / "scalim-viz" / "bad" / "viz_snapshot.json"
    bad_events_path = out_dir / "scalim-viz" / "bad" / "viz_events.jsonl"

    assert workflow_snapshot_path.exists()
    assert workflow_events_path.exists()
    assert ok_snapshot_path.exists()
    assert ok_events_path.exists()
    assert not bad_snapshot_path.exists()
    assert not bad_events_path.exists()

    snapshot = json.loads(workflow_snapshot_path.read_text(encoding="utf-8"))
    nodes = {item.get("id"): item for item in snapshot.get("nodes") or []}
    ok_node = nodes.get("workflow_node:ok") or {}
    bad_node = nodes.get("workflow_node:bad") or {}

    assert ok_node.get("data", {}).get("kind") == "workflow_demand"
    assert ok_node.get("data", {}).get("demand_run_id") == "ok"

    assert bad_node.get("data", {}).get("kind") == "workflow_demand"
    assert "demand_run_id" not in (bad_node.get("data") or {})
