import json
from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import (
    BookBudgetPolicy,
    BookResourcePolicy,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    ResourcesPolicy,
    RunOverrides,
    WorkflowRunOptions,
    run_workflow,
)
from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError
from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRuntimeOptions
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

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_main_fast"
  fields:
    ref_id: {{extract: ref_id}}
""".format(name=str(name))
        ).lstrip(),
    )


def _write_table_demand_yaml_with_book_output(tmp_path: Path, *, file_name: str, name: str, book_id: str) -> Path:
    return _write_text(
        tmp_path / file_name,
        (
            f"""
name: {name}

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_table_a_fast"
  fields:
    id: {{extract: id}}
    value: {{extract: value}}

outputs:
  - name: detail
    to:
      book: {book_id}
      sheet: detail
    fields: ["id", "value"]
"""
        ).lstrip(),
    )


def _write_bad_demand_yaml(tmp_path: Path, *, file_name: str, name: str) -> Path:
    # This YAML is loadable, but compilation should fail because the Python reference is invalid.
    return _write_text(
        tmp_path / file_name,
        (
            """
name: {name}

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:no_such_function"
  fields:
    ref_id: {{extract: ref_id}}
""".format(name=str(name))
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
""".format(
                demand_ok=str(demand_ok),
                demand_missing=str(demand_missing),
            )
        ).lstrip(),
    )


def _workflow_runtime_options(*, failure_policy: str = "all_fail", max_concurrency: int = 1) -> WorkflowRuntimeOptions:
    return WorkflowRuntimeOptions(
        execution=WorkflowExecutionOptions(max_concurrency=int(max_concurrency), failure_policy=str(failure_policy))
    )


def test_workflow_viz_bundle_exports_linked_runs(tmp_path: Path) -> None:
    _ = _write_minimal_demand_yaml(tmp_path, file_name="ok.yaml", name="ok")
    _ = _write_bad_demand_yaml(tmp_path, file_name="bad.yaml", name="bad")
    wf = _write_workflow_yaml(tmp_path, file_name="wf.yaml", demand_ok="ok.yaml", demand_missing="bad.yaml")

    out_dir = tmp_path / "out"

    options = WorkflowRunOptions(
        demand=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
            outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(output_dir=str(out_dir)))),
        ),
        runtime=_workflow_runtime_options(failure_policy="primary_only"),
    )
    result = run_workflow(
        str(wf),
        options=options,
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


def test_workflow_viz_bundle_rejects_explicit_paths(tmp_path: Path) -> None:
    _ = _write_minimal_demand_yaml(tmp_path, file_name="ok.yaml", name="ok")
    wf = _write_workflow_yaml(tmp_path, file_name="wf.yaml", demand_ok="ok.yaml", demand_missing="ok.yaml")

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        options = WorkflowRunOptions(
            demand=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                outputs=DemandRunOutputOptions(
                    overrides=RunOverrides(viz_config=VizObserverConfig(output_path=str(tmp_path / "viz_events.jsonl")))
                ),
            ),
            runtime=_workflow_runtime_options(failure_policy="primary_only"),
        )
        _ = run_workflow(
            str(wf),
            options=options,
        )

    assert exc_info.value.path == "run_workflow.options.demand.outputs.overrides.viz_config"


def test_workflow_viz_bundle_requires_output_dir_or_default(tmp_path: Path) -> None:
    _ = _write_minimal_demand_yaml(tmp_path, file_name="ok.yaml", name="ok")
    wf = _write_workflow_yaml(tmp_path, file_name="wf.yaml", demand_ok="ok.yaml", demand_missing="ok.yaml")

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        options = WorkflowRunOptions(
            demand=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig())),
            ),
            runtime=_workflow_runtime_options(failure_policy="primary_only"),
        )
        _ = run_workflow(
            str(wf),
            options=options,
        )

    assert exc_info.value.path == "run_workflow.options.demand.outputs.overrides.viz_config"


def test_workflow_viz_bundle_uses_default_output_dir_and_skips_write_nodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.ob.presets._internal import viz_config as viz_config_module

    default_dir = tmp_path / "default"
    monkeypatch.setattr(viz_config_module, "default_viz_dir", lambda: str(default_dir))

    _ = _write_table_demand_yaml_with_book_output(tmp_path, file_name="ok.yaml", name="ok", book_id="report")
    wf = _write_text(
        tmp_path / "wf.yaml",
        (
            f"""
workflow:
  resources:
    books:
      report:
        xlsx_memory: {{}}
  runs:
    - id: ok
      demand: ok.yaml
"""
        ).lstrip(),
    )

    result = run_workflow(
        str(wf),
        options=WorkflowRunOptions(
            demand=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(use_default_output_dir=True))),
            ),
            runtime=_workflow_runtime_options(failure_policy="primary_only"),
            resources_policy=ResourcesPolicy(
                books={"report": BookResourcePolicy(budget=BookBudgetPolicy(max_sheets=10, max_total_cells=1000))},
            ),
        ),
    )
    assert not result.errors()

    workflow_snapshot_path = default_dir / "scalim-viz" / "workflow" / "viz_snapshot.json"
    assert workflow_snapshot_path.exists()
