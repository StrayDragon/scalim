from __future__ import annotations

import tempfile
from pathlib import Path
from typing import FrozenSet

from scalim.dsl.by_yaml import Compilation, OutputOverrides, RunOverrides, RunResult, run_workflow
from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.dsl.by_yaml import run as run_yaml
from scalim.sinks.sink_memory import InMemoryRowSink

from .._types import EXAMPLE_KIND_ORACLE, ExampleResult
from ._fixtures import get_preload_counter_calls, reset_preload_counter_calls

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXPECTED_WORKFLOW_RUNS = 2


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run_public_api_dsl_by_yaml() -> ExampleResult:
    """覆盖 `scalim.dsl.by_yaml.__all__` 的最小示例: `compile`/`run`/`run_workflow` + overrides.

    目标:
    - YAML demand 可 deterministically 运行并产出行数据(内存 sink)
    - workflow 可 deterministically 运行,并对 `share_preload_cache=true` 提供可观察断言点
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"
        workflow_path = tmp / "workflow.yaml"

        demand_yaml = """\
name: public_api_minimal_demand
batch_size: 2

main_source:
  source_id: items
  loader: "scalim_misc.examples.public_api._fixtures:load_items"
  fields:
    item_id: {extract: item_id, name: Item ID}
    dim_id: {extract: dim_id, name: Dim ID}

sources:
  dims:
    loader: "scalim_misc.examples.public_api._fixtures:load_dims"
    key: dim_id
    cache_mode: preload_forever
"""
        _write_text(demand_path, demand_yaml)

        workflow_yaml = """\
workflow:
  runs:
    - id: r1
      demand: demand.yaml
    - id: r2
      demand: demand.yaml
  options:
    max_concurrency: 2
    share_preload_cache: true
"""
        _write_text(workflow_path, workflow_yaml)

        compilation: Compilation = compile_yaml(str(demand_path), allowed_modules=_ALLOWED_MODULES)
        if not compilation or not compilation.demand_ir.fields:
            return ExampleResult(
                example_id="public_api/dsl_by_yaml",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile returned empty IR",
            )

        sink = InMemoryRowSink()
        overrides = RunOverrides(output=OutputOverrides(path=None))
        result: RunResult = run_yaml(
            str(demand_path),
            allowed_modules=_ALLOWED_MODULES,
            sink=sink,
            overrides=overrides,
        )
        rows = sink.get_data()
        if not rows:
            return ExampleResult(
                example_id="public_api/dsl_by_yaml",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="run produced no rows",
                details={"result": result},
            )
        if rows[0].get("item_id") != 1:
            return ExampleResult(
                example_id="public_api/dsl_by_yaml",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="unexpected first row item_id",
                details={"first_row": rows[0]},
            )

        reset_preload_counter_calls()
        wf = run_workflow(
            str(workflow_path),
            allowed_modules=_ALLOWED_MODULES,
            max_workers=0,
            runtime_vars={},
        )
        preload_calls = get_preload_counter_calls()
        errors = wf.errors()
        passed = bool(not errors and preload_calls == 1 and len(wf.outcomes) == _EXPECTED_WORKFLOW_RUNS)
        summary = "rows={} workflow_outcomes={} preload_calls={} errors={}".format(len(rows), len(wf.outcomes), preload_calls, len(errors))
        if errors:
            summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)

        return ExampleResult(
            example_id="public_api/dsl_by_yaml",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details={"workflow_outcomes": wf.outcomes, "preload_calls": preload_calls, "errors": errors},
        )
