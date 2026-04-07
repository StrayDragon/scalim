from pathlib import Path
from typing import Any

import pytest

from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.workflow import execute as workflow_execute_mod
from scalim.ob.observer import Observer
from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr

_ALLOWED_MODULES = frozenset(["tests.fixtures.workflow_loaders"])


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _write_min_demand_yaml(tmp_path: Path, *, file_name: str) -> Path:
    return _write_text(
        tmp_path / file_name,
        (
            """
name: d1

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_main_fast"
  fields:
    ref_id:
      name: ref_id

sources:
  preload:
    loader: "tests.fixtures.workflow_loaders:load_preload_table"
    key: id
    cache_mode: preload_forever
    fields:
      value:
        name: value
        relation: main_to_preload

relations:
  main_to_preload:
    steps:
      - from: main.ref_id
        to: preload.id
"""
        ).lstrip(),
    )


def _write_min_workflow_yaml(tmp_path: Path, *, demand_path: Path) -> Path:
    return _write_text(
        tmp_path / "workflow.yaml",
        (
            """
workflow:
  runs:
    - id: a
      demand: {demand_file}
  options:
    max_concurrency: 1
    failure_policy: all_fail
    cache_pool:
      conflict_policy: warn
      release_policy: dag_refcount
      budget:
        max_entries: 1
        over_budget_policy: fail_fast
"""
        )
        .format(demand_file=str(demand_path.name))
        .lstrip(),
    )


class _BadObserver(Observer):
    # `ObserverManager.register` 会校验 `event_types` 为 `Set[str]` 或 `None`.
    # 这里故意传入错误类型,触发 `workflow_execute._build_workflow_instrumentation` 的异常清理分支.
    event_types = []  # type: ignore[assignment]

    def on_event(self, event) -> None:  # type: ignore[override]
        _ = event


def test_build_workflow_instrumentation_closes_manager_on_register_error() -> None:
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    with pytest.raises(TypeError):
        _ = workflow_execute_mod._build_workflow_instrumentation(  # type: ignore[attr-defined]
            workflow_exec_id="wf_test",
            workflow_path="workflow.yaml",
            workflow_ir=workflow_ir,
            max_concurrency=1,
            components=[_BadObserver()],
            bundle_viz_base_config=None,
        )


def test_prepare_workflow_run_closes_cache_pool_and_observers_on_error(tmp_path: Path, monkeypatch) -> None:
    demand_path = _write_min_demand_yaml(tmp_path, file_name="a.yaml")
    wf_path = _write_min_workflow_yaml(tmp_path, demand_path=demand_path)

    def _boom(*args: Any, **kwargs: Any) -> object:
        _ = args, kwargs
        raise RuntimeError("boom")

    monkeypatch.setattr(workflow_execute_mod, "WorkflowResourceManager", _boom)

    with pytest.raises(RuntimeError, match="boom"):
        _ = run_workflow(str(wf_path), options=RunOptions(allowed_modules=_ALLOWED_MODULES))
