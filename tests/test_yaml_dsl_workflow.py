import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import pytest

from scalim.dsl.by_yaml import run_workflow
from scalim.dsl.by_yaml.runtime import workflow_entrypoints as entrypoints_mod
from scalim.events.catalog import (
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_PIPELINE_START,
    EVENT_WORKFLOW_CACHE_ACQUIRE,
    EVENT_WORKFLOW_CACHE_EVICT,
    EVENT_WORKFLOW_CACHE_RELEASE,
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
    EVENT_WORKFLOW_RESOURCE_COMMIT,
    EVENT_WORKFLOW_RESOURCE_CREATE,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
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
        EVENT_DIAGNOSTIC_WARNING,
        EVENT_PIPELINE_START,
        EVENT_WORKFLOW_CACHE_ACQUIRE,
        EVENT_WORKFLOW_CACHE_EVICT,
        EVENT_WORKFLOW_CACHE_RELEASE,
        EVENT_WORKFLOW_NODE_START,
        EVENT_WORKFLOW_NODE_END,
        EVENT_WORKFLOW_NODE_CANCELLED,
        EVENT_WORKFLOW_RESOURCE_CREATE,
        EVENT_WORKFLOW_RESOURCE_WRITE,
        EVENT_WORKFLOW_RESOURCE_COMMIT,
        EVENT_WORKFLOW_RESOURCE_DISCARD,
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


def _cache_pool_config(
    *,
    conflict_policy: str = "error",
    release_policy: str = "dag_refcount",
    max_entries: int = 10,
    over_budget_policy: str = "fail_fast",
    pin: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "conflict_policy": str(conflict_policy),
        "release_policy": str(release_policy),
        "budget": {
            "max_entries": int(max_entries),
            "over_budget_policy": str(over_budget_policy),
        },
    }
    if pin:
        cfg["pin"] = pin
    return cfg


def _write_demand_yaml(
    tmp_path: Path,
    *,
    file_name: str,
    name: str,
    main_loader_ref: str,
    preload_loader_ref: str,
    cache_mode: str = "preload_forever",
    preload_source_id: str = "preload",
    preload_params_yaml: Optional[str] = None,
) -> Path:
    preload_params_block = ""
    if preload_params_yaml:
        snippet = str(preload_params_yaml).strip("\n")
        indented = "\n".join(("    " + line if line.strip() else "") for line in snippet.splitlines())
        preload_params_block = "{}\n".format(indented)

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
  {preload_source_id}:
    loader: "{preload_loader_ref}"
    key: id
    cache_mode: {cache_mode}
{preload_params_block}
    fields:
      value:
        name: value
        relation: main_to_preload

relations:
  main_to_preload:
    steps:
      - from: main.ref_id
        to: {preload_source_id}.id
"""
        )
        .format(
            name=name,
            main_loader_ref=main_loader_ref,
            preload_loader_ref=preload_loader_ref,
            cache_mode=cache_mode,
            preload_source_id=preload_source_id,
            preload_params_block=preload_params_block,
        )
        .lstrip(),
    )


def _write_table_demand_yaml_with_csv_output(
    tmp_path: Path,
    *,
    file_name: str,
    name: str,
    loader_ref: str,
    output_name: str,
    output_path: Path,
    field_ids: List[str],
) -> Path:
    field_lines = []
    for fid in field_ids:
        field_lines.append("    {}: {{extract: {}}}".format(str(fid), str(fid)))

    return _write_text(
        tmp_path / file_name,
        (
            """
name: {name}

main_source:
  source_id: main
  loader: "{loader_ref}"
  fields:
{fields}

outputs:
  - name: {output_name}
    container:
      type: csv
      path: "{output_path}"
    fields: {fields_list}
"""
        )
        .format(
            name=str(name),
            loader_ref=str(loader_ref),
            fields="\n".join(field_lines),
            output_name=str(output_name),
            output_path=str(output_path),
            fields_list=json.dumps([str(x) for x in field_ids]),
        )
        .lstrip(),
    )


def _write_workflow_yaml(
    tmp_path: Path,
    *,
    runs: list,
    max_concurrency: int = 1,
    failure_policy: str = "all_fail",
    resources: Optional[Dict[str, Any]] = None,
    cache_pool: Optional[Dict[str, Any]] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Path:
    run_lines = []
    for item in runs:
        depends_on = item.get("depends_on") or []
        depends_on_lines = ""
        if depends_on:
            depends_on_lines = "\n      depends_on:\n{}".format("\n".join(["        - {}".format(d) for d in depends_on]))

        init_vars = cast("Optional[Dict[str, object]]", item.get("init_vars"))
        init_vars_lines = ""
        if init_vars:
            rendered = []
            for key, value in init_vars.items():
                rendered.append("        {}: {}".format(str(key), json.dumps(value)))
            init_vars_lines = "\n      init_vars:\n{}".format("\n".join(rendered))

        write_to = cast("Any", item.get("write_to"))
        write_to_lines = ""
        if write_to:
            if not isinstance(write_to, dict) or len(write_to) != 1:
                raise ValueError("write_to must be a mapping with exactly one key")
            kind = next(iter(write_to.keys()))
            cfg = write_to.get(kind) or {}
            if not isinstance(cfg, dict):
                raise ValueError("write_to.<kind> must be a mapping")
            cfg_lines = []
            for key, value in cfg.items():
                cfg_lines.append("          {}: {}".format(str(key), json.dumps(value)))
            write_to_lines = "\n      write_to:\n        {}:\n{}".format(str(kind), "\n".join(cfg_lines))

        run_lines.append(
            "    - id: {}\n      demand: {}{}{}{}".format(item["id"], item["demand"], depends_on_lines, init_vars_lines, write_to_lines)
        )

    resources_lines = ""
    if resources:
        group_lines: List[str] = []
        for group_key, group_cfg in resources.items():
            group_lines.append("    {}:".format(str(group_key)))
            for res_id, cfg in cast("Dict[str, Any]", group_cfg).items():
                group_lines.append("      {}:".format(str(res_id)))
                for key, value in cast("Dict[str, Any]", cfg).items():
                    group_lines.append("        {}: {}".format(str(key), json.dumps(value)))
        resources_lines = "\n  resources:\n{}".format("\n".join(group_lines))

    cache_pool_lines = ""
    if cache_pool is not None:
        budget = cast("Dict[str, Any]", cache_pool.get("budget") or {})
        max_entries = int(budget.get("max_entries", 1))
        over_budget_policy = str(budget.get("over_budget_policy", "fail_fast"))
        pins = cast("List[Dict[str, Any]]", cache_pool.get("pin") or [])
        pin_lines = ""
        if pins:
            pin_item_lines = []
            for pin in pins:
                pin_item_lines.append(
                    "        - kind: {kind}\n          source_id: {source_id}".format(
                        kind=str(pin.get("kind", "")),
                        source_id=str(pin.get("source_id", "")),
                    )
                )
            pin_lines = "\n      pin:\n{}".format("\n".join(pin_item_lines))
        cache_pool_lines = (
            "\n    cache_pool:\n"
            "      conflict_policy: {conflict_policy}\n"
            "      release_policy: {release_policy}\n"
            "      budget:\n"
            "        max_entries: {max_entries}\n"
            "        over_budget_policy: {over_budget_policy}{pin_lines}"
        ).format(
            conflict_policy=str(cache_pool.get("conflict_policy", "")),
            release_policy=str(cache_pool.get("release_policy", "")),
            max_entries=max_entries,
            over_budget_policy=over_budget_policy,
            pin_lines=pin_lines,
        )

    ctx_lines = ""
    if ctx is not None:
        ctx_lines = ("\n    ctx:\n      max_value_bytes: {max_value_bytes}\n      max_bytes: {max_bytes}").format(
            max_value_bytes=int(ctx.get("max_value_bytes", 65536)),
            max_bytes=int(ctx.get("max_bytes", 1048576)),
        )
    return _write_text(
        tmp_path / "workflow.yaml",
        (
            """
workflow:
  runs:
{runs}
{resources_lines}
  options:
    max_concurrency: {max_concurrency}
    failure_policy: {failure_policy}
{cache_pool_lines}
{ctx_lines}
"""
        )
        .format(
            runs="\n".join(run_lines),
            resources_lines=resources_lines.rstrip(),
            max_concurrency=max_concurrency,
            failure_policy=failure_policy,
            cache_pool_lines=cache_pool_lines.rstrip(),
            ctx_lines=ctx_lines.rstrip(),
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


def test_load_workflow_config_rejects_unknown_depends_on(tmp_path: Path) -> None:
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
      depends_on: [nope]
"""
        ).lstrip(),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "Unknown run.depends_on id" in str(excinfo.value)


def test_load_workflow_config_rejects_depends_on_cycles(tmp_path: Path) -> None:
    workflow_path = _write_text(
        tmp_path / "wf.yaml",
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
      depends_on: [b]
    - id: b
      demand: b.yaml
      depends_on: [a]
"""
        ).lstrip(),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "cycle_path" in str(excinfo.value)
    assert '["a", "b", "a"]' in str(excinfo.value)


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
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert [o.run_id for o in result.outcomes] == ["slow", "fast"]


def test_workflow_dag_respects_depends_on_under_concurrency(tmp_path: Path) -> None:
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
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml", "depends_on": ["a"]}],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert [o.run_id for o in result.outcomes] == ["a", "b"]

    start = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_START]
    end = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_END]

    by_start = {e.payload.workflow_node_id: e for e in start}
    by_end = {e.payload.workflow_node_id: e for e in end}

    assert by_start["b"].seq > by_end["a"].seq


def test_workflow_ctx_init_vars_are_resolved_after_prereq_completion(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="up.yaml",
        name="up",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_slow",
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
        preload_params_yaml=(
            """
params:
  p:
    $init_var: token
"""
        ).strip(),
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[
            {"id": "up", "demand": "up.yaml"},
            {
                "id": "down",
                "demand": "down.yaml",
                "depends_on": ["up"],
                "init_vars": {
                    "token": {
                        "$ctx": {"node": "up", "key": "total_rows"},
                    }
                },
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()

    start = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_START]
    end = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_NODE_END]
    by_start = {e.payload.workflow_node_id: e for e in start}
    by_end = {e.payload.workflow_node_id: e for e in end}
    assert by_start["down"].seq > by_end["up"].seq


def test_workflow_ctx_ref_outside_depends_on_closure_fails_fast(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="c.yaml",
        name="c",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[
            {"id": "a", "demand": "a.yaml"},
            {
                "id": "c",
                "demand": "c.yaml",
                "init_vars": {"token": {"$ctx": {"node": "a", "key": "total_rows"}}},
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    with pytest.raises(WorkflowConfigError, match="declare depends_on"):
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)


def test_workflow_ctx_ref_node_self_fails_fast(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[
            {
                "id": "a",
                "demand": "a.yaml",
                "init_vars": {"token": {"$ctx": {"node": "a", "key": "total_rows"}}},
            }
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )

    with pytest.raises(WorkflowConfigError, match="node=self"):
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)


def test_workflow_ctx_ref_unknown_node_fails_fast(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
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
        runs=[
            {"id": "a", "demand": "a.yaml"},
            {
                "id": "b",
                "demand": "b.yaml",
                "init_vars": {"token": {"$ctx": {"node": "nope", "key": "total_rows"}}},
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    with pytest.raises(WorkflowConfigError, match="Unknown ctx node"):
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)


def test_workflow_ctx_guardrails_fail_fast(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        cache_mode="none",
    )

    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}],
        max_concurrency=1,
        failure_policy="primary_only",
        ctx={"max_value_bytes": 1, "max_bytes": 10},
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert result.errors()
    assert result.outcomes[0].error is not None
    assert result.outcomes[0].error.exc_type == "WorkflowConfigError"
    assert "max_value_bytes" in result.outcomes[0].error.message


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
            {"id": "down", "demand": "down.yaml", "depends_on": ["bad"]},
        ],
        max_concurrency=2,
        failure_policy="primary_only",
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
            {"id": "child", "demand": "child.yaml", "depends_on": ["bad", "slow"]},
        ],
        max_concurrency=2,
        failure_policy="all_fail",
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


def test_cache_pool_reuses_preload_forever_across_runs(tmp_path: Path) -> None:
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
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="error", release_policy="dag_refcount", max_entries=10),
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 1

    acquires = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_ACQUIRE]
    acquires.sort(key=lambda e: e.seq)
    assert [e.payload.cache_status for e in acquires] == ["miss", "hit"]
    assert {e.payload.workflow_node_id for e in acquires} == {"a", "b"}

    releases = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_RELEASE]
    assert {e.payload.workflow_node_id for e in releases} == {"a", "b"}

    evicts = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_EVICT]
    assert len(evicts) == 1
    assert evicts[0].payload.reason == "refcount_zero"
    assert evicts[0].payload.workflow_node_id == "b"


def test_cache_pool_conflict_policy_error_fails_fast(tmp_path: Path) -> None:
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
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="error", release_policy="dag_refcount", max_entries=10),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)

    msg = str(excinfo.value)
    assert "cache_pool signature conflict" in msg and "diff=" in msg
    assert "loader_ref" in msg
    assert workflow_loaders.preload_calls() == 1


def test_cache_pool_conflict_policy_separate_runs_and_warns(tmp_path: Path) -> None:
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
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="separate", release_policy="dag_refcount", max_entries=10),
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 2

    warnings = [e for e in recorder.events if e.event_type == EVENT_DIAGNOSTIC_WARNING]
    assert warnings

    acquires = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_ACQUIRE]
    assert any(e.payload.conflict_detected is True for e in acquires)


def test_cache_pool_signature_uses_rendered_params_for_reuse(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        preload_params_yaml=(
            """
params:
  p:
    $init_var: token
"""
        ).strip(),
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="b.yaml",
        name="b",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table",
        preload_params_yaml=(
            """
params:
  p: 1
"""
        ).strip(),
    )

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml"}],
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="error", release_policy="dag_refcount", max_entries=10),
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder], init_vars={"token": 1})
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 1

    acquires = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_ACQUIRE]
    assert acquires
    assert all(e.payload.conflict_detected is False for e in acquires)


def test_cache_pool_signature_includes_lookup_cast_meta(tmp_path: Path) -> None:
    demand_template = (
        """
name: demo

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
    lookup_cast:
      name: sep_first
      sep: "{sep}"
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
    ).lstrip()

    _ = _write_text(tmp_path / "a.yaml", demand_template.format(sep=","))
    _ = _write_text(tmp_path / "b.yaml", demand_template.format(sep=";"))

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml"}],
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="error", release_policy="dag_refcount", max_entries=10),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert "lookup_cast" in str(excinfo.value)


def test_cache_pool_budget_evict_lru_evicts_idle_entry(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="a.yaml",
        name="a",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table_alt",
        preload_source_id="preload_a",
    )
    _ = _write_demand_yaml(
        tmp_path,
        file_name="b.yaml",
        name="b",
        main_loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        preload_loader_ref="tests.fixtures.workflow_loaders:load_preload_table_alt",
        preload_source_id="preload_b",
    )

    workflow_loaders.reset_counters()
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": "a.yaml"}, {"id": "b", "demand": "b.yaml"}],
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(
            conflict_policy="error",
            release_policy="workflow_end",
            max_entries=1,
            over_budget_policy="evict_lru",
        ),
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 2

    evicts = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_EVICT]
    assert any(e.payload.reason == "budget_lru" for e in evicts)
    assert any(e.payload.reason == "workflow_end" for e in evicts)


def test_cache_pool_budget_fail_fast_raises(tmp_path: Path) -> None:
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
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(
            conflict_policy="separate",
            release_policy="workflow_end",
            max_entries=1,
            over_budget_policy="fail_fast",
        ),
    )

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert "over budget" in str(excinfo.value).lower()
    assert workflow_loaders.preload_calls() == 1


def test_cache_pool_pin_keeps_entry_until_workflow_end(tmp_path: Path) -> None:
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
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(
            conflict_policy="error",
            release_policy="dag_refcount",
            max_entries=10,
            pin=[{"kind": "preload_forever", "source_id": "preload"}],
        ),
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 1

    evicts = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_EVICT]
    assert evicts
    assert any(e.payload.reason == "workflow_end" for e in evicts)
    assert not any(e.payload.reason == "refcount_zero" for e in evicts)


def test_cache_pool_calls_node_done_on_compile_error_and_cancelled_dependents(tmp_path: Path) -> None:
    _ = _write_demand_yaml(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        main_loader_ref="tests.fixtures.workflow_loaders:missing_loader",
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
        runs=[{"id": "bad", "demand": "bad.yaml"}, {"id": "ok", "demand": "ok.yaml", "depends_on": ["bad"]}],
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="warn", release_policy="dag_refcount", max_entries=10),
    )
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert [o.run_id for o in result.outcomes] == ["bad", "ok"]
    assert result.outcomes[0].error is not None
    assert result.outcomes[1].error is not None
    assert result.outcomes[1].error.exc_type == "WorkflowCancelled"


def test_cache_pool_calls_node_done_on_runtime_error(tmp_path: Path) -> None:
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
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="warn", release_policy="dag_refcount", max_entries=10),
    )
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert [o.run_id for o in result.outcomes] == ["bad"]
    assert result.outcomes[0].error is not None
    assert result.outcomes[0].error.exc_type == "ValueError"


def test_workflow_schema_validation() -> None:
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

    ok_cache_pool = yaml.safe_load(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
  options:
    max_concurrency: 1
    failure_policy: all_fail
    cache_pool:
      conflict_policy: error
      release_policy: dag_refcount
      budget:
        max_entries: 1
        over_budget_policy: fail_fast
"""
        ).lstrip()
    )
    jsonschema.validate(ok_cache_pool, schema)

    ok_ctx_and_depends_on = yaml.safe_load(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
    - id: b
      demand: b.yaml
      depends_on: [a]
      init_vars:
        token:
          $ctx:
            node: a
            key: total_rows
  options:
    ctx:
      max_value_bytes: 65536
      max_bytes: 1048576
"""
        ).lstrip()
    )
    jsonschema.validate(ok_ctx_and_depends_on, schema)

    bad_legacy_deps = yaml.safe_load(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
      deps: [b]
"""
        ).lstrip()
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_legacy_deps, schema)

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

    bad_share_preload_cache = yaml.safe_load(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
  options:
    share_preload_cache: true
"""
        ).lstrip()
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_share_preload_cache, schema)

    bad_cache_pool = yaml.safe_load(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
  options:
    cache_pool:
      conflict_policy: nope
      release_policy: dag_refcount
      budget:
        max_entries: 1
        over_budget_policy: fail_fast
"""
        ).lstrip()
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_cache_pool, schema)


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


@pytest.mark.parametrize(
    ("options", "path"),
    [
        ({"share_preload_cache": True}, "workflow.options.share_preload_cache"),
        ({"cache_pool": []}, "workflow.options.cache_pool"),
        (
            {
                "cache_pool": {
                    "conflict_policy": "nope",
                    "release_policy": "dag_refcount",
                    "budget": {"max_entries": 1, "over_budget_policy": "fail_fast"},
                }
            },
            "workflow.options.cache_pool.conflict_policy",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "nope",
                    "budget": {"max_entries": 1, "over_budget_policy": "fail_fast"},
                }
            },
            "workflow.options.cache_pool.release_policy",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": [],
                }
            },
            "workflow.options.cache_pool.budget",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": True, "over_budget_policy": "fail_fast"},
                }
            },
            "workflow.options.cache_pool.budget.max_entries",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": "x", "over_budget_policy": "fail_fast"},
                }
            },
            "workflow.options.cache_pool.budget.max_entries",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": 0, "over_budget_policy": "fail_fast"},
                }
            },
            "workflow.options.cache_pool.budget.max_entries",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": 1, "over_budget_policy": "nope"},
                }
            },
            "workflow.options.cache_pool.budget.over_budget_policy",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": 1, "over_budget_policy": "fail_fast"},
                    "pin": {},
                }
            },
            "workflow.options.cache_pool.pin",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": 1, "over_budget_policy": "fail_fast"},
                    "pin": ["x"],
                }
            },
            "workflow.options.cache_pool.pin.0",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": 1, "over_budget_policy": "fail_fast"},
                    "pin": [{"kind": "nope", "source_id": "s1"}],
                }
            },
            "workflow.options.cache_pool.pin.0.kind",
        ),
        (
            {
                "cache_pool": {
                    "conflict_policy": "warn",
                    "release_policy": "workflow_end",
                    "budget": {"max_entries": 1, "over_budget_policy": "fail_fast"},
                    "pin": [{"kind": "preload_forever", "source_id": ""}],
                }
            },
            "workflow.options.cache_pool.pin.0.source_id",
        ),
    ],
)
def test_load_workflow_config_from_mapping_rejects_invalid_cache_pool_options(options: Dict[str, Any], path: str) -> None:
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": options}})
    assert excinfo.value.path == path


def test_load_workflow_config_from_mapping_accepts_null_options() -> None:
    cfg = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "options": None}})
    assert cfg.options.max_concurrency == 1


def test_load_workflow_config_from_mapping_accepts_ctx_options() -> None:
    cfg = load_workflow_config_from_mapping(
        {
            "workflow": {
                "runs": [{"id": "a", "demand": "a.yaml"}],
                "options": {
                    "ctx": {
                        "max_value_bytes": 2,
                        "max_bytes": 3,
                    }
                },
            }
        }
    )
    assert cfg.options.ctx.max_value_bytes == 2
    assert cfg.options.ctx.max_bytes == 3


@pytest.mark.parametrize(
    ("ctx", "path"),
    [
        ([], "workflow.options.ctx"),
        ({"max_value_bytes": 0, "max_bytes": 1}, "workflow.options.ctx.max_value_bytes"),
        ({"max_value_bytes": "nope", "max_bytes": 1}, "workflow.options.ctx.max_value_bytes"),
        ({"max_value_bytes": 1, "max_bytes": 0}, "workflow.options.ctx.max_bytes"),
        ({"max_value_bytes": 1, "max_bytes": "nope"}, "workflow.options.ctx.max_bytes"),
        ({"max_value_bytes": True, "max_bytes": 1}, "workflow.options.ctx.max_value_bytes"),
        ({"max_value_bytes": 1, "max_bytes": True}, "workflow.options.ctx.max_bytes"),
    ],
)
def test_load_workflow_config_from_mapping_rejects_invalid_ctx_options(ctx: object, path: str) -> None:
    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [{"id": "a", "demand": "a.yaml"}],
                    "options": {
                        "ctx": ctx,
                    },
                }
            }
        )
    assert excinfo.value.path == path


def test_load_workflow_config_from_mapping_rejects_legacy_deps_field() -> None:
    with pytest.raises(WorkflowConfigError, match="run\\.deps was removed; use run\\.depends_on") as excinfo:
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml", "deps": ["b"]},
                    ]
                }
            }
        )
    assert excinfo.value.path == "workflow.runs.0.deps"


def test_load_workflow_config_from_mapping_rejects_depends_on_not_list() -> None:
    with pytest.raises(WorkflowConfigError, match="run\\.depends_on must be a list"):
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml", "depends_on": "nope"},
                    ]
                }
            }
        )


def test_load_workflow_config_from_mapping_rejects_depends_on_empty_item() -> None:
    with pytest.raises(WorkflowConfigError, match="depends_on items must be non-empty"):
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml"},
                        {"id": "b", "demand": "b.yaml", "depends_on": [""]},
                    ]
                }
            }
        )


def test_load_workflow_config_from_mapping_dedups_depends_on_preserves_first_order() -> None:
    cfg = load_workflow_config_from_mapping(
        {
            "workflow": {
                "runs": [
                    {"id": "a", "demand": "a.yaml"},
                    {"id": "b", "demand": "b.yaml", "depends_on": ["a", "a"]},
                ]
            }
        }
    )
    assert cfg.runs[1].depends_on == ("a",)


def test_load_workflow_config_from_mapping_accepts_forward_depends_on() -> None:
    cfg = load_workflow_config_from_mapping(
        {
            "workflow": {
                "runs": [
                    {"id": "b", "demand": "b.yaml", "depends_on": ["a"]},
                    {"id": "a", "demand": "a.yaml"},
                ]
            }
        }
    )
    assert [r.id for r in cfg.runs] == ["b", "a"]


def test_load_workflow_config_from_mapping_rejects_init_vars_not_mapping() -> None:
    with pytest.raises(WorkflowConfigError, match="run\\.init_vars must be a mapping") as excinfo:
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml", "init_vars": []},
                    ]
                }
            }
        )
    assert excinfo.value.path == "workflow.runs.0.init_vars"


def test_load_workflow_config_from_mapping_rejects_init_vars_key_invalid() -> None:
    with pytest.raises(WorkflowConfigError, match="run\\.init_vars keys must be non-empty strings") as excinfo:
        _ = load_workflow_config_from_mapping(
            {
                "workflow": {
                    "runs": [
                        {"id": "a", "demand": "a.yaml", "init_vars": {"": 1}},
                    ]
                }
            }
        )
    assert excinfo.value.path == "workflow.runs.0.init_vars"


def test_load_workflow_config_from_mapping_accepts_null_resources() -> None:
    cfg = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": None}})
    assert cfg.resources.workbooks == {}
    assert cfg.resources.csvs == {}


def test_load_workflow_config_from_mapping_accepts_resources_mapping() -> None:
    cfg = load_workflow_config_from_mapping(
        {
            "workflow": {
                "runs": [{"id": "a", "demand": "a.yaml"}],
                "resources": {
                    "workbooks": {"report": {"path": "./out/report.xlsx"}},
                    "csvs": {"merged": {"path": "./out/merged.csv"}},
                },
            }
        }
    )
    assert cfg.resources.workbooks["report"].path == "./out/report.xlsx"
    assert cfg.resources.csvs["merged"].path == "./out/merged.csv"


def test_load_workflow_config_from_mapping_rejects_resources_not_mapping() -> None:
    with pytest.raises(WorkflowConfigError, match="workflow.resources must be a mapping"):
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": []}})


def test_load_workflow_config_from_mapping_rejects_resources_key_invalid() -> None:
    with pytest.raises(WorkflowConfigError, match="workflow\\.resources keys must be non-empty"):
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml"}], "resources": {"": {"kind": "x"}}}})


def test_load_workflow_config_from_mapping_rejects_self_depends_on() -> None:
    with pytest.raises(WorkflowConfigError, match="self dependency"):
        _ = load_workflow_config_from_mapping({"workflow": {"runs": [{"id": "a", "demand": "a.yaml", "depends_on": ["a"]}]}})


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
    )

    with pytest.raises(Exception) as excinfo:
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert "run_id=bad" in str(excinfo.value)


def test_workflow_entrypoints_artifacts_directory_enforces_visibility() -> None:
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowEdgeIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr

    ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml"),
            WorkflowNodeIr(node_id="b", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=("a",), demand_path="b.yaml"),
        ),
        edges=(WorkflowEdgeIr(from_node_id="a", to_node_id="b"),),
        options=WorkflowOptionsIr(),
        resources=(),
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


def test_workflow_entrypoints_ensure_json_like_variants() -> None:
    assert entrypoints_mod._ensure_json_like(None, path="x") is None  # noqa: SLF001
    assert entrypoints_mod._ensure_json_like(True, path="x") is True  # noqa: SLF001
    assert entrypoints_mod._ensure_json_like(1, path="x") == 1  # noqa: SLF001
    assert entrypoints_mod._ensure_json_like("s", path="x") == "s"  # noqa: SLF001
    assert entrypoints_mod._ensure_json_like(1.5, path="x") == 1.5  # noqa: SLF001

    assert entrypoints_mod._ensure_json_like([1, {"k": 2}], path="x") == [1, {"k": 2}]  # noqa: SLF001
    assert entrypoints_mod._ensure_json_like((1, 2), path="x") == [1, 2]  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="finite"):
        _ = entrypoints_mod._ensure_json_like(float("inf"), path="x")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="dict key"):
        _ = entrypoints_mod._ensure_json_like({1: "x"}, path="x")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="JSON-like"):
        _ = entrypoints_mod._ensure_json_like(object(), path="x")  # noqa: SLF001


def test_workflow_entrypoints_ctx_store_total_bytes_guardrail() -> None:
    from scalim.spec.ir.workflow import (
        WorkflowArtifactsIr,
        WorkflowCtxOptionsIr,
        WorkflowEdgeIr,
        WorkflowIr,
        WorkflowNodeIr,
        WorkflowNodeType,
        WorkflowOptionsIr,
    )

    ir = WorkflowIr(
        nodes=(WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml"),),
        edges=(),
        options=WorkflowOptionsIr(ctx=WorkflowCtxOptionsIr(max_value_bytes=1000, max_bytes=5)),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": ()}),
    )
    ctx_store = entrypoints_mod._WorkflowCtxStore(ir)  # noqa: SLF001
    ctx_store.publish("a", "k1", "x", path="x")  # noqa: SLF001
    with pytest.raises(WorkflowConfigError) as excinfo:
        ctx_store.publish("a", "k2", "y", path="x")  # noqa: SLF001
    assert excinfo.value.path == "workflow.options.ctx.max_bytes"


def test_workflow_entrypoints_ctx_store_resolve_errors() -> None:
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowEdgeIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr

    ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml"),
            WorkflowNodeIr(node_id="b", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=("a",), demand_path="b.yaml"),
        ),
        edges=(WorkflowEdgeIr(from_node_id="a", to_node_id="b"),),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "b": ()}),
    )
    ctx_store = entrypoints_mod._WorkflowCtxStore(ir)  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="node=self"):
        _ = ctx_store.resolve("a", node="a", key="k", path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="not visible"):
        _ = ctx_store.resolve("a", node="b", key="k", path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="Unknown ctx key"):
        _ = ctx_store.resolve("b", node="a", key="missing", path="p")  # noqa: SLF001


def test_workflow_entrypoints_iter_ctx_directives_variants() -> None:
    with pytest.raises(WorkflowConfigError, match="directive must be a mapping"):
        _ = entrypoints_mod._iter_ctx_directives({"$ctx": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="\\$ctx\\.node"):
        _ = entrypoints_mod._iter_ctx_directives({"$ctx": {"node": "", "key": "k"}}, path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="\\$ctx\\.key"):
        _ = entrypoints_mod._iter_ctx_directives({"$ctx": {"node": "a", "key": ""}}, path="p")  # noqa: SLF001

    assert entrypoints_mod._iter_ctx_directives({"outer": {"$ctx": {"node": "a", "key": "k"}}}, path="p") == [  # noqa: SLF001
        ("a", "k"),
    ]
    assert entrypoints_mod._iter_ctx_directives([{"$ctx": {"node": "a", "key": "k"}}], path="p") == [  # noqa: SLF001
        ("a", "k"),
    ]


def test_workflow_entrypoints_render_ctx_directives_variants() -> None:
    from scalim.spec.ir.workflow import WorkflowArtifactsIr, WorkflowEdgeIr, WorkflowIr, WorkflowNodeIr, WorkflowNodeType, WorkflowOptionsIr

    ir = WorkflowIr(
        nodes=(
            WorkflowNodeIr(node_id="a", node_type=WorkflowNodeType.DEMAND, decl_order=0, deps=(), demand_path="a.yaml"),
            WorkflowNodeIr(node_id="b", node_type=WorkflowNodeType.DEMAND, decl_order=1, deps=("a",), demand_path="b.yaml"),
        ),
        edges=(WorkflowEdgeIr(from_node_id="a", to_node_id="b"),),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={"a": (), "b": ()}),
    )
    ctx_store = entrypoints_mod._WorkflowCtxStore(ir)  # noqa: SLF001
    ctx_store.publish("a", "k", 1, path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="directive must be a mapping"):
        _ = entrypoints_mod._render_ctx_directives({"$ctx": "nope"}, consumer_node_id="b", ctx_store=ctx_store, path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="\\$ctx\\.node"):
        _ = entrypoints_mod._render_ctx_directives({"$ctx": {"node": "", "key": "k"}}, consumer_node_id="b", ctx_store=ctx_store, path="p")  # noqa: SLF001

    with pytest.raises(WorkflowConfigError, match="\\$ctx\\.key"):
        _ = entrypoints_mod._render_ctx_directives({"$ctx": {"node": "a", "key": ""}}, consumer_node_id="b", ctx_store=ctx_store, path="p")  # noqa: SLF001

    assert (
        entrypoints_mod._render_ctx_directives(
            {"outer": {"$ctx": {"node": "a", "key": "k"}}}, consumer_node_id="b", ctx_store=ctx_store, path="p"
        )  # noqa: SLF001
        == {"outer": 1}
    )
    assert (
        entrypoints_mod._render_ctx_directives([{"$ctx": {"node": "a", "key": "k"}}], consumer_node_id="b", ctx_store=ctx_store, path="p")  # noqa: SLF001
        == [1]
    )
    assert entrypoints_mod._render_ctx_directives(1, consumer_node_id="b", ctx_store=ctx_store, path="p") == 1  # noqa: SLF001


def test_cache_pool_single_run_accepts_lookup_cast_and_normalize(tmp_path: Path) -> None:
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
    loader: "tests.fixtures.workflow_loaders:load_preload_table"
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
    wf = _write_workflow_yaml(
        tmp_path,
        runs=[{"id": "a", "demand": str(demand_path)}],
        max_concurrency=1,
        failure_policy="primary_only",
        cache_pool=_cache_pool_config(conflict_policy="error", release_policy="dag_refcount", max_entries=10),
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workflow_loaders.preload_calls() == 1

    acquires = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_ACQUIRE]
    assert len(acquires) == 1
    assert acquires[0].payload.cache_status == "miss"

    evicts = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_CACHE_EVICT]
    assert len(evicts) == 1
    assert evicts[0].payload.reason == "refcount_zero"


def _read_xlsx_rows(path: Path, sheet: str) -> List[List[object]]:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb[str(sheet)]
        rows: List[List[object]] = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        return rows
    finally:
        wb.close()


def _read_csv_rows(path: Path) -> List[List[str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as handle:
        return [list(r) for r in csv.reader(handle)]


def test_workflow_shared_workbook_sheet_writes_commit_and_emit_events(tmp_path: Path) -> None:
    a_out = tmp_path / "a_detail.csv"
    b_out = tmp_path / "b_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="a.yaml",
        name="a",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=a_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="b.yaml",
        name="b",
        loader_ref="tests.fixtures.workflow_loaders:load_table_b_fast",
        output_name="detail",
        output_path=b_out,
        field_ids=["id", "value"],
    )

    workbook_path = tmp_path / "report.xlsx"
    wf = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {
                "id": "a",
                "demand": "a.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "A", "output": "detail"}},
            },
            {
                "id": "b",
                "demand": "b.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "B", "output": "detail"}},
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workbook_path.exists()
    assert not Path(str(workbook_path) + ".scalim.lock").exists()

    assert _read_xlsx_rows(workbook_path, "A") == [
        ["id", "value"],
        ["a1", "A1"],
        ["a2", "A2"],
    ]
    assert _read_xlsx_rows(workbook_path, "B") == [
        ["id", "value"],
        ["b1", "B1"],
        ["b2", "B2"],
    ]

    creates = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_RESOURCE_CREATE]
    writes = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_RESOURCE_WRITE]
    commits = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_RESOURCE_COMMIT]
    assert len(creates) == 1
    assert creates[0].payload.resource_id == "report"
    assert creates[0].payload.workflow_node_id == "__wf__write.0"
    assert len([e for e in writes if e.payload.resource_id == "report"]) == 2
    assert len([e for e in commits if e.payload.resource_id == "report"]) == 1
    assert commits[0].payload.workflow_node_id == "__wf__write.1"


def test_workflow_shared_workbook_append_is_deterministic_by_runs_order(tmp_path: Path) -> None:
    slow_out = tmp_path / "slow_detail.csv"
    fast_out = tmp_path / "fast_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="slow.yaml",
        name="slow",
        loader_ref="tests.fixtures.workflow_loaders:load_table_c_slow",
        output_name="detail",
        output_path=slow_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="fast.yaml",
        name="fast",
        loader_ref="tests.fixtures.workflow_loaders:load_table_b_fast",
        output_name="detail",
        output_path=fast_out,
        field_ids=["id", "value"],
    )

    workbook_path = tmp_path / "append.xlsx"
    wf = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {
                "id": "slow",
                "demand": "slow.yaml",
                "write_to": {
                    "workbook_append": {
                        "workbook": "report",
                        "sheet": "All",
                        "output": "detail",
                        "header_policy": "once",
                        "on_mismatch": "error",
                    }
                },
            },
            {
                "id": "fast",
                "demand": "fast.yaml",
                "write_to": {
                    "workbook_append": {
                        "workbook": "report",
                        "sheet": "All",
                        "output": "detail",
                        "header_policy": "once",
                        "on_mismatch": "error",
                    }
                },
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert workbook_path.exists()

    assert _read_xlsx_rows(workbook_path, "All") == [
        ["id", "value"],
        ["c1", "C1"],
        ["b1", "B1"],
        ["b2", "B2"],
    ]

    write_events = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_RESOURCE_WRITE and e.payload.resource_id == "report"]
    assert [e.payload.workflow_node_id for e in write_events] == ["__wf__write.0", "__wf__write.1"]


def test_workflow_shared_append_header_policy_variants(tmp_path: Path) -> None:
    a_out = tmp_path / "a_detail.csv"
    b_out = tmp_path / "b_detail.csv"
    c_out = tmp_path / "c_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="a.yaml",
        name="a",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=a_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="b.yaml",
        name="b",
        loader_ref="tests.fixtures.workflow_loaders:load_table_b_fast",
        output_name="detail",
        output_path=b_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="c.yaml",
        name="c",
        loader_ref="tests.fixtures.workflow_loaders:load_table_c_slow",
        output_name="detail",
        output_path=c_out,
        field_ids=["id", "value"],
    )

    workbook_path = tmp_path / "policies.xlsx"
    wf = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {
                "id": "a",
                "demand": "a.yaml",
                "write_to": {"workbook_append": {"workbook": "report", "sheet": "All", "output": "detail", "header_policy": "once"}},
            },
            {
                "id": "b",
                "demand": "b.yaml",
                "write_to": {"workbook_append": {"workbook": "report", "sheet": "All", "output": "detail", "header_policy": "always"}},
            },
            {
                "id": "c",
                "demand": "c.yaml",
                "write_to": {"workbook_append": {"workbook": "report", "sheet": "All", "output": "detail", "header_policy": "never"}},
            },
        ],
        max_concurrency=3,
        failure_policy="primary_only",
    )

    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert not result.errors()

    assert _read_xlsx_rows(workbook_path, "All") == [
        ["id", "value"],
        ["a1", "A1"],
        ["a2", "A2"],
        ["id", "value"],
        ["b1", "B1"],
        ["b2", "B2"],
        ["c1", "C1"],
    ]


def test_workflow_shared_csv_append_warn_skip_and_header_policies(tmp_path: Path) -> None:
    a_out = tmp_path / "a_detail.csv"
    b_out = tmp_path / "b_detail.csv"
    m_out = tmp_path / "m_detail.csv"
    m2_out = tmp_path / "m2_detail.csv"

    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="a.yaml",
        name="a",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=a_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="b.yaml",
        name="b",
        loader_ref="tests.fixtures.workflow_loaders:load_table_b_fast",
        output_name="detail",
        output_path=b_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="m.yaml",
        name="m",
        loader_ref="tests.fixtures.workflow_loaders:load_table_mismatch",
        output_name="detail",
        output_path=m_out,
        field_ids=["id", "other"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="m2.yaml",
        name="m2",
        loader_ref="tests.fixtures.workflow_loaders:load_table_mismatch",
        output_name="detail",
        output_path=m2_out,
        field_ids=["id", "other"],
    )

    merged_path = tmp_path / "merged.csv"
    wf = _write_workflow_yaml(
        tmp_path,
        resources={"csvs": {"merged": {"path": str(merged_path)}}},
        runs=[
            {
                "id": "a",
                "demand": "a.yaml",
                "write_to": {"csv_append": {"csv": "merged", "output": "detail", "header_policy": "once", "on_mismatch": "error"}},
            },
            {
                "id": "m",
                "demand": "m.yaml",
                "write_to": {"csv_append": {"csv": "merged", "output": "detail", "header_policy": "always", "on_mismatch": "warn"}},
            },
            {
                "id": "b",
                "demand": "b.yaml",
                "write_to": {"csv_append": {"csv": "merged", "output": "detail", "header_policy": "never", "on_mismatch": "error"}},
            },
            {
                "id": "m2",
                "demand": "m2.yaml",
                "write_to": {"csv_append": {"csv": "merged", "output": "detail", "header_policy": "once", "on_mismatch": "skip"}},
            },
        ],
        max_concurrency=4,
        failure_policy="primary_only",
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert not result.errors()
    assert merged_path.exists()

    assert _read_csv_rows(merged_path) == [
        ["id", "value"],
        ["a1", "A1"],
        ["a2", "A2"],
        ["id", "value"],
        ["m1", ""],
        ["b1", "B1"],
        ["b2", "B2"],
    ]

    skips = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_RESOURCE_WRITE and e.payload.action == "skip"]
    assert skips


def test_workflow_shared_resources_discard_on_failure(tmp_path: Path) -> None:
    ok_out = tmp_path / "ok_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=ok_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="bad.yaml",
        name="bad",
        loader_ref="tests.fixtures.workflow_loaders:load_table_raises",
        output_name="detail",
        output_path=tmp_path / "bad_detail.csv",
        field_ids=["id", "value"],
    )

    workbook_path = tmp_path / "discard.xlsx"
    wf = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {"id": "ok", "demand": "ok.yaml", "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "OK", "output": "detail"}}},
            {"id": "bad", "demand": "bad.yaml"},
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )

    recorder = _WorkflowEventRecorder()
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES, components=[recorder])
    assert result.errors()
    assert not workbook_path.exists()
    assert not Path(str(workbook_path) + ".scalim.lock").exists()

    discards = [e for e in recorder.events if e.event_type == EVENT_WORKFLOW_RESOURCE_DISCARD and e.payload.resource_id == "report"]
    assert discards


def test_workflow_shared_sheet_conflict_policies(tmp_path: Path) -> None:
    a_out = tmp_path / "a_detail.csv"
    b_out = tmp_path / "b_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="a.yaml",
        name="a",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=a_out,
        field_ids=["id", "value"],
    )
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="b.yaml",
        name="b",
        loader_ref="tests.fixtures.workflow_loaders:load_table_b_fast",
        output_name="detail",
        output_path=b_out,
        field_ids=["id", "value"],
    )

    # on_conflict=error
    workbook_err = tmp_path / "conflict_err.xlsx"
    wf_err = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_err)}}},
        runs=[
            {"id": "a", "demand": "a.yaml", "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}}},
            {
                "id": "b",
                "demand": "b.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail", "on_conflict": "error"}},
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )
    result_err = run_workflow(str(wf_err), allowed_modules=_ALLOWED_MODULES)
    assert result_err.errors()
    assert not workbook_err.exists()

    # on_conflict=overwrite
    workbook_over = tmp_path / "conflict_over.xlsx"
    wf_over = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_over)}}},
        runs=[
            {"id": "a", "demand": "a.yaml", "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}}},
            {
                "id": "b",
                "demand": "b.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail", "on_conflict": "overwrite"}},
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )
    result_over = run_workflow(str(wf_over), allowed_modules=_ALLOWED_MODULES)
    assert not result_over.errors()
    assert workbook_over.exists()
    assert _read_xlsx_rows(workbook_over, "S")[-1] == ["b2", "B2"]

    # on_conflict=skip
    workbook_skip = tmp_path / "conflict_skip.xlsx"
    wf_skip = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_skip)}}},
        runs=[
            {"id": "a", "demand": "a.yaml", "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}}},
            {
                "id": "b",
                "demand": "b.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail", "on_conflict": "skip"}},
            },
        ],
        max_concurrency=2,
        failure_policy="primary_only",
    )
    result_skip = run_workflow(str(wf_skip), allowed_modules=_ALLOWED_MODULES)
    assert not result_skip.errors()
    assert workbook_skip.exists()
    assert _read_xlsx_rows(workbook_skip, "S")[-1] == ["a2", "A2"]


def test_workflow_shared_output_lock_failure_fails_fast(tmp_path: Path) -> None:
    out = tmp_path / "a_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="a.yaml",
        name="a",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=out,
        field_ids=["id", "value"],
    )

    workbook_path = tmp_path / "locked.xlsx"
    lock_path = Path(str(workbook_path) + ".scalim.lock")
    lock_path.write_text("locked", encoding="utf-8")

    wf = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[{"id": "a", "demand": "a.yaml", "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}}}],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert result.errors()
    assert lock_path.exists()


def test_workflow_shared_write_node_validates_demand_outputs_mapping_and_output_id(tmp_path: Path) -> None:
    ok_out = tmp_path / "ok_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=ok_out,
        field_ids=["id", "value"],
    )
    no_outputs = _write_text(
        tmp_path / "no_outputs.yaml",
        (
            """
name: demo
main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_table_a_fast"
  fields:
    id: {extract: id}
    value: {extract: value}
"""
        ).lstrip(),
    )

    workbook_path = tmp_path / "validate.xlsx"

    wf_missing_outputs = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {"id": "a", "demand": str(no_outputs), "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}}}
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result_missing_outputs = run_workflow(str(wf_missing_outputs), allowed_modules=_ALLOWED_MODULES)
    assert result_missing_outputs.errors()

    wf_unknown_output_id = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[{"id": "ok", "demand": "ok.yaml", "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "nope"}}}],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result_unknown = run_workflow(str(wf_unknown_output_id), allowed_modules=_ALLOWED_MODULES)
    assert result_unknown.errors()


def test_workflow_shared_append_write_node_validates_outputs_mapping_and_output_id(tmp_path: Path) -> None:
    ok_out = tmp_path / "ok_detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=ok_out,
        field_ids=["id", "value"],
    )
    no_outputs = _write_text(
        tmp_path / "no_outputs.yaml",
        (
            """
name: demo
main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_table_a_fast"
  fields:
    id: {extract: id}
    value: {extract: value}
"""
        ).lstrip(),
    )

    workbook_path = tmp_path / "append_validate.xlsx"

    wf_missing_outputs = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {
                "id": "a",
                "demand": str(no_outputs),
                "write_to": {"workbook_append": {"workbook": "report", "sheet": "S", "output": "detail"}},
            }
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result_missing_outputs = run_workflow(str(wf_missing_outputs), allowed_modules=_ALLOWED_MODULES)
    assert result_missing_outputs.errors()

    wf_unknown_output_id = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {
                "id": "ok",
                "demand": "ok.yaml",
                "write_to": {"workbook_append": {"workbook": "report", "sheet": "S", "output": "nope"}},
            }
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result_unknown = run_workflow(str(wf_unknown_output_id), allowed_modules=_ALLOWED_MODULES)
    assert result_unknown.errors()


def test_workflow_shared_write_node_rejects_non_csv_output_paths(tmp_path: Path) -> None:
    out = tmp_path / "detail.txt"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="badext.yaml",
        name="badext",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=out,
        field_ids=["id", "value"],
    )

    workbook_path = tmp_path / "report.xlsx"
    wf_sheet = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path)}}},
        runs=[
            {
                "id": "a",
                "demand": "badext.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}},
            }
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result_sheet = run_workflow(str(wf_sheet), allowed_modules=_ALLOWED_MODULES)
    assert result_sheet.errors()

    workbook_path2 = tmp_path / "append.xlsx"
    wf_append = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_path2)}}},
        runs=[
            {
                "id": "a",
                "demand": "badext.yaml",
                "write_to": {"workbook_append": {"workbook": "report", "sheet": "S", "output": "detail"}},
            }
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    result_append = run_workflow(str(wf_append), allowed_modules=_ALLOWED_MODULES)
    assert result_append.errors()


def test_workflow_shared_resource_commit_failure_raises_workflow_config_error(tmp_path: Path) -> None:
    out = tmp_path / "detail.csv"
    _ = _write_table_demand_yaml_with_csv_output(
        tmp_path,
        file_name="ok.yaml",
        name="ok",
        loader_ref="tests.fixtures.workflow_loaders:load_table_a_fast",
        output_name="detail",
        output_path=out,
        field_ids=["id", "value"],
    )

    workbook_dir = tmp_path / "outdir"
    workbook_dir.mkdir()
    lock_path = Path(str(workbook_dir) + ".scalim.lock")

    wf = _write_workflow_yaml(
        tmp_path,
        resources={"workbooks": {"report": {"path": str(workbook_dir)}}},
        runs=[
            {
                "id": "a",
                "demand": "ok.yaml",
                "write_to": {"workbook_sheet": {"workbook": "report", "sheet": "S", "output": "detail"}},
            }
        ],
        max_concurrency=1,
        failure_policy="primary_only",
    )
    with pytest.raises(WorkflowConfigError, match="workflow.resources"):
        _ = run_workflow(str(wf), allowed_modules=_ALLOWED_MODULES)
    assert workbook_dir.exists()
    assert not lock_path.exists()
