import json
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List

import pytest

from scalim.dsl.by_yaml import run_workflow
from scalim.dsl.by_yaml.runtime import workflow_entrypoints as entrypoints_mod
from scalim.events.catalog import (
    EVENT_PIPELINE_START,
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
)
from scalim.hooks.base import BaseHook
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.dsl.by_yaml.workflow import (
    WorkflowConfigError,
    load_workflow_config,
    load_workflow_config_from_mapping,
    resolve_workflow_demand_path,
    validate_workflow_yaml_text_json,
)
from tests.fixtures import workflow_loaders


_ALLOWED_MODULES = frozenset(["tests.fixtures.workflow_loaders"])


class _WorkflowEventRecorder(Observer):
    event_types = {
        EVENT_PIPELINE_START,
        EVENT_WORKFLOW_NODE_START,
        EVENT_WORKFLOW_NODE_END,
        EVENT_WORKFLOW_NODE_CANCELLED,
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: List[Any] = []

    def on_event(self, event) -> None:  # type: ignore[override]
        with self._lock:
            self.events.append(event)


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _write_demand_yaml(
    tmp_path: Path,
    *,
    file_name: str,
    name: str,
    main_loader_ref: str,
    preload_loader_ref: str,
    cache_mode: str = "preload_forever",
) -> Path:
    return _write_text(
        tmp_path / file_name,
        (
            """
name: {name}

main_source:
  source_id: main
  loader: "{main_loader_ref}"
  fields:
    ref_id:
      name: ref_id

sources:
  preload:
    loader: "{preload_loader_ref}"
    key: id
    cache_mode: {cache_mode}
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
        )
        .format(
            name=name,
            main_loader_ref=main_loader_ref,
            preload_loader_ref=preload_loader_ref,
            cache_mode=cache_mode,
        )
        .lstrip(),
    )


def _write_workflow_yaml(
    tmp_path: Path,
    *,
    runs: list,
    max_concurrency: int = 1,
    failure_policy: str = "all_fail",
    share_preload_cache: bool = False,
) -> Path:
    run_lines = []
    for item in runs:
        deps = item.get("deps") or []
        deps_lines = ""
        if deps:
            deps_lines = "\n      deps:\n{}".format("\n".join(["        - {}".format(d) for d in deps]))
        run_lines.append("    - id: {}\n      demand: {}{}".format(item["id"], item["demand"], deps_lines))
    return _write_text(
        tmp_path / "workflow.yaml",
        (
            """
workflow:
  runs:
{runs}
  options:
    max_concurrency: {max_concurrency}
    failure_policy: {failure_policy}
    share_preload_cache: {share_preload_cache}
"""
        )
        .format(
            runs="\n".join(run_lines),
            max_concurrency=max_concurrency,
            failure_policy=failure_policy,
            share_preload_cache="true" if share_preload_cache else "false",
        )
        .lstrip(),
    )


def test_load_workflow_config_semantic_validation(tmp_path: Path) -> None:
    workflow_path = _write_text(
        tmp_path / "wf.yaml",
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
    - id: a
      demand: b.yaml
"""
        ).lstrip(),
    )

    with pytest.raises(WorkflowConfigError):
        _ = load_workflow_config(str(workflow_path))


def test_load_workflow_config_rejects_unknown_deps(tmp_path: Path) -> None:
    workflow_path = _write_text(
        tmp_path / "wf.yaml",
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
    - id: b
      demand: b.yaml
      deps: [nope]
"""
        ).lstrip(),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "Unknown run.deps id" in str(excinfo.value)


def test_load_workflow_config_rejects_deps_cycles(tmp_path: Path) -> None:
    workflow_path = _write_text(
        tmp_path / "wf.yaml",
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
      deps: [b]
    - id: b
      demand: b.yaml
      deps: [a]
"""
        ).lstrip(),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "cycles" in str(excinfo.value)


def test_run_workflow_primary_only_collects_errors(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "ok", "demand": "ok.yaml"}, {"id": "bad", "demand": "bad.yaml"}],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert [o.run_id for o in result.outcomes] == ["ok", "bad"]
    assert result.outcomes[0].result is not None
    assert result.outcomes[0].error is None
    assert result.outcomes[1].result is None
    assert result.outcomes[1].error is not None
    assert result.outcomes[1].error.exc_type in {"ValueError", "WorkflowRunFailedError", "RuntimeError"}
    assert result.errors()


def test_run_workflow_all_fail_raises(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "bad", "demand": "bad.yaml"}],
        max_concurrency=1,
        failure_policy="all_fail",
        share_preload_cache=False,
    )

    with pytest.raises(Exception) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)

    assert "run_id=bad" in str(excinfo.value)


def test_workflow_outcomes_are_in_declared_order(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="slow.yaml",
        name="slow",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_slow",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="fast.yaml",
        name="fast",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "slow", "demand": "slow.yaml"}, {"id": "fast", "demand": "fast.yaml"}],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert [o.run_id for o in result.outcomes] == ["slow", "fast"]


def test_workflow_dag_respects_deps_under_concurrency(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_slow",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="b.yaml",
        name="b",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml", "deps": ["a"]}],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert [o.run_id for o in result.outcomes] == ["a", "b"]

    start = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_START]
    end = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_END]

    by_start = {e.payload.workflow_node_id: e for e in start}
    by_end = {e.payload.workflow_node_id: e for e in end}

    assert by_start["b"].seq > by_end["a"].seq


def test_workflow_primary_only_cancels_downstream_when_dep_fails(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="down.yaml",
        name="down",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[
            {"id": "bad", "demand": "bad.yaml"},
            {"id": "down", "demand": "down.yaml", "deps": ["bad"]},
        ],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert [o.run_id for o in result.outcomes] == ["bad", "down"]
    assert result.outcomes[0].error is not None
    assert result.outcomes[1].result is None
    assert result.outcomes[1].error is not None
    assert "dependency" in result.outcomes[1].error.message.lower()

    cancelled = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0].payload.workflow_node_id == "down"
    assert cancelled[0].payload.reason == "dependency_failed"


def test_workflow_observability_bridge_injects_meta_and_emits_workflow_events(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="slow.yaml",
        name="slow",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_slow",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="fast.yaml",
        name="fast",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "slow", "demand": "slow.yaml"}, {"id": "fast", "demand": "fast.yaml"}],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    recorder = _WorkflowEventRecorder()
    _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])

    workflow_start = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_START]
    workflow_end = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_END]
    pipeline_start = [e for e in recorder.events if e.event_type == EVENT_PIPELINE_START]

    assert {e.payload.workflow_node_id for e in workflow_start} == {"slow", "fast"}
    assert {e.payload.workflow_node_id for e in workflow_end} == {"slow", "fast"}
    assert {e.meta.get("workflow_node_id") for e in pipeline_start} == {"slow", "fast"}

    workflow_exec_id = workflow_start[0].meta.get("workflow_exec_id")
    assert workflow_exec_id

    for event in workflow_start + workflow_end:
        assert event.run_id == workflow_exec_id
        assert event.meta.get("workflow_exec_id") == workflow_exec_id
        assert event.meta.get("workflow_node_id") in {"slow", "fast"}
        assert event.payload.workflow_exec_id == workflow_exec_id

    for event in pipeline_start:
        assert event.meta.get("workflow_exec_id") == workflow_exec_id
        assert event.meta.get("workflow_node_id") in {"slow", "fast"}
        assert event.run_id != workflow_exec_id
        assert str(event.run_id).startswith("run_")
        assert event.seq >= 1


def test_workflow_observability_bridge_emits_cancelled_reason_for_all_fail(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "bad", "demand": "bad.yaml"}, {"id": "ok", "demand": "ok.yaml"}],
        max_concurrency=1,
        failure_policy="all_fail",
        share_preload_cache=False,
    )

    recorder = _WorkflowEventRecorder()
    with pytest.raises(Exception):
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])

    cancelled = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0].payload.workflow_node_id == "ok"
    assert cancelled[0].payload.reason == "policy_all_fail"
    assert "failure_policy=all_fail" in cancelled[0].payload.message


def test_workflow_all_fail_skips_already_cancelled_nodes_on_late_terminal(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="slow.yaml",
        name="slow",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_slow",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="child.yaml",
        name="child",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[
            {"id": "bad", "demand": "bad.yaml"},
            {"id": "slow", "demand": "slow.yaml"},
            {"id": "child", "demand": "child.yaml", "deps": ["bad", "slow"]},
        ],
        max_concurrency=2,
        failure_policy="all_fail",
        share_preload_cache=False,
    )

    recorder = _WorkflowEventRecorder()
    with pytest.raises(Exception):
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])

    cancelled = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0].payload.workflow_node_id == "child"
    assert cancelled[0].payload.reason == "policy_all_fail"

    ended = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_END]
    assert any(e.payload.workflow_node_id == "slow" for e in ended)


def test_workflow_all_fail_compile_error_marks_end_and_cancels_pending(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:missing_loader",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "bad", "demand": "bad.yaml"}, {"id": "ok", "demand": "ok.yaml"}],
        max_concurrency=2,
        failure_policy="all_fail",
        share_preload_cache=False,
    )

    recorder = _WorkflowEventRecorder()
    with pytest.raises(Exception) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert "run_id=bad" in str(excinfo.value)

    ended = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_END]
    by_node = {e.payload.workflow_node_id: e for e in ended}
    assert by_node["bad"].payload.status == "error"

    cancelled = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0].payload.workflow_node_id == "ok"
    assert cancelled[0].payload.reason == "policy_all_fail"


def test_observer_manager_workflow_attribution_keys_fail_fast_on_override() -> None:
    manager = ObserverManager(
        run_id="x",
        event_meta_defaults={
            "workflow_exec_id": "wf_1",
            "workflow_node_id": "a",
        },
    )
    with pytest.raises(ValueError, match="workflow attribution"):
        manager.emit_event("x", 1, meta={"workflow_node_id": "b"})


def test_observer_manager_workflow_attribution_meta_merges_non_reserved_meta() -> None:
    manager = ObserverManager(
        run_id="x",
        event_meta_defaults={
            "workflow_exec_id": "wf_1",
            "workflow_node_id": "a",
        },
    )
    event = manager.emit_event("x", 1, meta={"worker_id": "w1"})
    assert event.meta == {
        "workflow_exec_id": "wf_1",
        "workflow_node_id": "a",
        "worker_id": "w1",
    }


def test_workflow_observability_bridge_registers_hooks(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="fast.yaml",
        name="fast",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "fast", "demand": "fast.yaml"}],
        max_concurrency=1,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    class _HookRecorder(BaseHook):
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.events: List[Any] = []

        def on_event(self, event) -> None:  # type: ignore[override]
            with self._lock:
                self.events.append(event)

    hook = _HookRecorder()
    _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[hook])
    assert any(e.event_type == EVENT_WORKFLOW_NODE_START for e in hook.events)


def test_share_preload_cache_loads_once(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="b.yaml",
        name="b",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml"}],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=True,
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 1


def test_share_preload_cache_conflict_fails_fast(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="b.yaml",
        name="b",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table_alt",
    )

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml"}],
        max_concurrency=2,
        failure_policy="primary_only",
        share_preload_cache=True,
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)

    msg = str(excinfo.value)
    assert "run 'a'" in msg and "run 'b'" in msg and "diff=" in msg
    assert workflow_loaders.preload_calls() == 0


def test_workflow_schema_validation(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    yaml = pytest.importorskip("yaml")

    from scalim.dsl.by_yaml.schema_dsl.builder import build_workflow_schema

    schema = build_workflow_schema()
    ok = yaml.safe_load(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
"""
        ).lstrip()
    )
    jsonschema.validate(ok, schema)

    bad = yaml.safe_load(
        (
            """
workflow:
  runs: []
"""
        ).lstrip()
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_workflow_config_error_formats_without_path() -> None:
    assert str(WorkflowConfigError("msg")) == "msg"


def test_load_workflow_config_wraps_read_errors(tmp_path: Path) -> None:
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(tmp_path))
    assert "Failed to read workflow YAML" in str(excinfo.value)


def test_load_workflow_config_wraps_yaml_parse_errors(tmp_path: Path) -> None:
    workflow_path = _write_text(tmp_path / "wf.yaml", "workflow: [\n")
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "YAML parse error" in str(excinfo.value)


def test_load_workflow_config_root_must_be_mapping(tmp_path: Path) -> None:
    workflow_path = _write_text(tmp_path / "wf.yaml", "- 1\n")
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "root must be a mapping" in str(excinfo.value)


def test_resolve_workflow_demand_path_requires_non_empty_string(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = resolve_workflow_demand_path("", workflow_yaml_path=str(wf))
    assert "run.demand must be a non-empty string" in str(excinfo.value)


def test_resolve_workflow_demand_path_supports_at_alias(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    demand = resolve_workflow_demand_path(
        "@/a.yaml",
        workflow_yaml_path=str(wf),
        path_aliases={"@": str(tmp_path)},
        run_id="r1",
    )
    assert demand == (tmp_path / "a.yaml").resolve(strict=False)


def test_resolve_workflow_demand_path_supports_named_alias(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    demand = resolve_workflow_demand_path(
        "DATA:/b.yaml",
        workflow_yaml_path=str(wf),
        path_aliases={"DATA": str(tmp_path)},
        run_id="r1",
    )
    assert demand == (tmp_path / "b.yaml").resolve(strict=False)


def test_resolve_workflow_demand_path_rejects_unknown_alias(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = resolve_workflow_demand_path(
            "DATA:/b.yaml",
            workflow_yaml_path=str(wf),
            path_aliases={},
            run_id="r1",
        )
    assert "Unknown path alias" in str(excinfo.value)
    assert "run_id=r1" in str(excinfo.value)


def test_resolve_workflow_demand_path_rejects_empty_at_alias_path(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = resolve_workflow_demand_path(
            "@/",
            workflow_yaml_path=str(wf),
            path_aliases={"@": str(tmp_path)},
            run_id="r1",
        )
    assert "Invalid demand alias path" in str(excinfo.value)
    assert "run_id=r1" in str(excinfo.value)


def test_resolve_workflow_demand_path_supports_absolute_paths(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    abs_path = (tmp_path / "abs.yaml").resolve(strict=False)
    demand = resolve_workflow_demand_path(str(abs_path), workflow_yaml_path=str(wf))
    assert demand == abs_path


def test_resolve_workflow_demand_path_supports_paths_relative_to_workflow(tmp_path: Path) -> None:
    wf = tmp_path / "workflow.yaml"
    demand = resolve_workflow_demand_path("rel.yaml", workflow_yaml_path=str(wf))
    assert demand == (tmp_path / "rel.yaml").resolve(strict=False)


def test_validate_workflow_yaml_text_json_variants() -> None:
    bad_parse = json.loads(validate_workflow_yaml_text_json("workflow: [\n"))
    assert bad_parse["ok"] is False

    empty = json.loads(validate_workflow_yaml_text_json(""))
    assert empty["ok"] is False
    assert "empty" in empty["errors"][0]["message"].lower()

    root_not_mapping = json.loads(validate_workflow_yaml_text_json("- 1\n"))
    assert root_not_mapping["ok"] is False

    semantic_error = json.loads(validate_workflow_yaml_text_json("workflow: {}\n"))
    assert semantic_error["ok"] is False
    assert semantic_error["errors"]

    ok = json.loads(
        validate_workflow_yaml_text_json(
            (
                """
workflow:
  runs:
    - id: a
      demand: a.yaml
"""
            ).lstrip()
        )
    )
    assert ok["ok"] is True


@pytest.mark.parametrize(
    "bad_mapping",
    [
        {},
        {"workflow": {}},
        {"workflow": {"runs": []}},
        {"workflow": {"runs": [1]}},
        {"workflow": {"runs": [{"id": "", "demand": "a.yaml"}]}},
        {"workflow": {"runs": [{"id": "a", "demand": ""}]}},
        {"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": []}},
        {"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": {"max_concurrency": True}}},
        {"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": {"max_concurrency": "x"}}},
        {"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": {"max_concurrency": 0}}},
        {"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": {"failure_policy": "nope"}}},
    ],
)
def test_load_workflow_config_from_mapping_rejects_invalid_structures(bad_mapping: dict) -> None:
    with pytest.raises(WorkflowConfigError):
        _ = load_workflow_config_from_mapping(bad_mapping)


def test_load_workflow_config_from_mapping_accepts_null_options() -> None:
    cfg = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": None}})
    assert cfg.options.max_concurrency == 1


def test_load_workflow_config_from_mapping_rejects_deps_not_list() -> None:
    with pytest.raises(WorkflowConfigError, match="run.deps must be a list"):
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml", "deps": "nope"},
                    ]
                }
            }
        )


def test_load_workflow_config_from_mapping_rejects_deps_empty_item() -> None:
    with pytest.raises(WorkflowConfigError, match="deps items must be non-empty"):
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml"},
                        {"id": "b", "demand": "b.yaml", "deps": [""]},
                    ]
                }
            }
        )


def test_load_workflow_config_from_mapping_rejects_deps_duplicates() -> None:
    with pytest.raises(WorkflowConfigError, match="must not contain duplicates"):
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml"},
                        {"id": "b", "demand": "b.yaml", "deps": ["a", "a"]},
                    ]
                }
            }
        )


def test_load_workflow_config_from_mapping_accepts_null_resources() -> None:
    cfg = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": None}})
    assert cfg.resources == {}


def test_load_workflow_config_from_mapping_accepts_resources_mapping() -> None:
    cfg = load_workflow_config_from_mapping(
        {"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": {"r1": {"kind": "demo"}}}}
    )
    assert cfg.resources == {"r1": {"kind": "demo"}}


def test_load_workflow_config_from_mapping_rejects_resources_not_mapping() -> None:
    with pytest.raises(WorkflowConfigError, match="workflow.resources must be a mapping"):
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": []}})


def test_load_workflow_config_from_mapping_rejects_resources_key_invalid() -> None:
    with pytest.raises(WorkflowConfigError, match="resources keys must be non-empty"):
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": {"": {"kind": "x"}}}})


def test_load_workflow_config_from_mapping_rejects_self_deps() -> None:
    with pytest.raises(WorkflowConfigError, match="self dependency"):
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml", "deps": ["a"]}]}})


def test_run_workflow_requires_workflow_path(tmp_path: Path) -> None:
    _ = tmp_path
    with pytest.raises(WorkflowConfigError):
        _ = run_workflow("", allowed_modules=_ALLOWED_MODULES)


def test_run_workflow_primary_only_submits_pending_after_failure(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="ok1.yaml",
        name="ok1",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="ok2.yaml",
        name="ok2",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "bad", "demand": "bad.yaml"}, {"id": "ok1", "demand": "ok1.yaml"}, {"id": "ok2", "demand": "ok2.yaml"}],
        max_concurrency=1,
        failure_policy="primary_only",
        share_preload_cache=False,
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert [o.run_id for o in result.outcomes] == ["bad", "ok1", "ok2"]
    assert result.outcomes[0].error is not None
    assert result.outcomes[1].result is not None
    assert result.outcomes[2].result is not None


def test_run_workflow_all_fail_cancels_pending_queue(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_raises",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "bad", "demand": "bad.yaml"}, {"id": "ok", "demand": "ok.yaml"}],
        max_concurrency=1,
        failure_policy="all_fail",
        share_preload_cache=False,
    )

    with pytest.raises(Exception) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert "run_id=bad" in str(excinfo.value)


def test_workflow_entrypoints_internal_helpers_are_covered() -> None:
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowEdgeIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr

    with pytest.raises(entrypoints_mod.ResolverError):
        _ = entrypoints_mod._normalize_python_reference(".demo.mod.func", base_module_path=None)  # noqa: SLF001

    assert (
        entrypoints_mod._normalize_python_reference(".a.b:Obj.m", base_module_path="pkg")  # noqa: SLF001
        == "pkg.a.b:Obj.m"
    )
    assert (
        entrypoints_mod._normalize_python_reference(".a.b.func", base_module_path="pkg")  # noqa: SLF001
        == "pkg.a.b.func"
    )

    with pytest.raises(entrypoints_mod.ResolverError):
        _ = entrypoints_mod._normalize_relative_module_path("...x", base_module_path="a", reference="...x.f")  # noqa: SLF001

    assert (
        entrypoints_mod._render_preload_forever_params(  # noqa: SLF001
            "src",
            params={},
            init_vars=None,
            path="sources.src.params",
        )
        == {}
    )

    with pytest.raises(WorkflowConfigError):
        _ = entrypoints_mod._render_preload_forever_params(  # noqa: SLF001
            "src",
            params={"$keys": None},
            init_vars=None,
            path="sources.src.params",
        )

    with pytest.raises(WorkflowConfigError):
        _ = entrypoints_mod._render_preload_forever_params(  # noqa: SLF001
            "src",
            params=1,
            init_vars=None,
            path="sources.src.params",
        )

    assert entrypoints_mod._ensure_json_like([1], path="p") == [1]  # noqa: SLF001

    with pytest.raises(WorkflowConfigError):
        _ = entrypoints_mod._ensure_json_like({1: "x"}, path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError):
        _ = entrypoints_mod._ensure_json_like(set([1]), path="p")  # noqa: SLF001

    ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml"),
            WorkflowNodeIr(node_id="b", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=("a",), demand_path="b.yaml"),
        ),
        edges=(WorkflowEdgeIr(from_node_id="a", to_node_id="b"),),
        options=WorkflowOptionsIr(),
        resources={},
        artifacts=WorkflowArtifactsIr(
            slots_by_node_id={
                "a": ("output_path", "outputs"),
                "b": ("output_path", "outputs"),
            }
        ),
    )
    artifacts_dir = entrypoints_mod._WorkflowArtifactsDirectory(ir)  # noqa: SLF001
    artifacts_dir.publish("a", "x", 1)  # noqa: SLF001
    assert artifacts_dir.get("b", "a", "x") == 1  # noqa: SLF001

    artifacts_dir.publish("b", "y", 2)  # noqa: SLF001
    assert artifacts_dir.get("b", "b", "y") == 2  # noqa: SLF001

    with pytest.raises(ValueError, match="not visible"):
        _ = artifacts_dir.get("a", "b", "y")  # noqa: SLF001

    with pytest.raises(KeyError, match="Unknown artifact"):
        _ = artifacts_dir.get("b", "a", "missing")  # noqa: SLF001


def test_share_preload_cache_precheck_skips_when_single_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", [str(tmp_path)] + list(sys.path))

    demand_path = _write_text(
        tmp_path / "demand.yaml",
        (
            """
name: demo

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_main_fast"
  fields:
    ref_id:
      name: ref_id

sources:
  other:
    loader: "tests.fixtures.workflow_loaders:load_preload_table"
    key: id
    cache_mode: none
  preload:
    loader: ".tests.fixtures.workflow_loaders:load_preload_table"
    key: id
    cache_mode: preload_forever
    lookup_cast:
      name: sep_first
      sep: ","
    normalize:
      kind: index_by_key
      key_field: id
      on_conflict: last
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

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(tmp_path, runs=[{"id": "a", "demand": str(demand_path)}], share_preload_cache=True)

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert not result.errors()
