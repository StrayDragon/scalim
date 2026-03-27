import marimo

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from scalim.events import EVENT_LOADER_CALL, EVENT_PIPELINE_END, EVENT_PIPELINE_START
from scalim.execution.run_ir import ExecutionRequest, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim.hooks import BaseHook
from scalim.ob.observer import Observer
from scalim.sinks import InMemoryRowSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir

__generated_with = "0.20.2"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch180_public_api_hooks_events"


@dataclass
class _HookStats:
    pipeline_start: int = 0
    pipeline_end: int = 0
    loader_calls: List[str] = field(default_factory=list)


class _CounterHook(BaseHook):
    def __init__(self) -> None:
        self.event_types: Optional[Set[str]] = {EVENT_PIPELINE_START, EVENT_PIPELINE_END, EVENT_LOADER_CALL}
        self.stats = _HookStats()

    def on_pipeline_start(self, event: Any) -> None:
        _ = event
        self.stats.pipeline_start += 1

    def on_pipeline_end(self, event: Any) -> None:
        _ = event
        self.stats.pipeline_end += 1

    def on_loader_call(self, event: Any) -> None:
        loader_name = getattr(event, "loader_name", None)
        if loader_name:
            self.stats.loader_calls.append(str(loader_name))


class _TraceObserver(Observer):
    def __init__(self) -> None:
        self.event_types: Optional[Set[str]] = {EVENT_PIPELINE_START, EVENT_PIPELINE_END, EVENT_LOADER_CALL}
        self.seen_event_types: List[str] = []

    def on_event(self, event: Any) -> None:
        self.seen_event_types.append(str(getattr(event, "event_type", "")))


def run_public_api_hooks_events() -> ExampleResult:
    demand_ir = build_minimal_public_api_ir()
    export_layout = export_layout_from_demand_ir(
        demand_ir,
        ("item_id", "dim_id", "value_plus_one"),
        header_fields_output_by="field_id",
    )

    sink = InMemoryRowSink()
    hook = _CounterHook()
    observer = _TraceObserver()
    request = ExecutionRequest(
        export_layout=export_layout,
        output=OutputSpec(path=None),
        sink=sink,
        output_composition=None,
        observability=None,
        guardrails=None,
        loader_retry=None,
        components=[observer, hook],
        batch_size=10,
        parallel_mode="seq",
        max_workers=0,
    )
    core = run_ir(demand_ir, request)
    rows = sink.get_data()

    passed = bool(
        core.total_rows == len(rows) == 3
        and rows
        and rows[0].get("value_plus_one") == 2
        and hook.stats.pipeline_start == 1
        and hook.stats.pipeline_end == 1
        and hook.stats.loader_calls == ["items"]
        and observer.seen_event_types.count(EVENT_PIPELINE_START) == 1
        and observer.seen_event_types.count(EVENT_PIPELINE_END) == 1
        and observer.seen_event_types.count(EVENT_LOADER_CALL) == 1
    )
    summary = "rows={} hook(pipeline_start={}, pipeline_end={}, loader_calls={}) observer_events={}".format(
        len(rows),
        hook.stats.pipeline_start,
        hook.stats.pipeline_end,
        len(hook.stats.loader_calls),
        len(observer.seen_event_types),
    )
    details: Dict[str, Any] = {
        "event_types": list(observer.seen_event_types),
        "hook": {
            "pipeline_start": hook.stats.pipeline_start,
            "pipeline_end": hook.stats.pipeline_end,
            "loader_calls": list(hook.stats.loader_calls),
        },
        "rows": rows,
    }
    return ExampleResult(
        example_id=_EXAMPLE_ID,
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_hooks_events()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch180_public_api_hooks_events

        本章目标:
        - 演示扩展点: hook / observer / events / components 注入

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch180_public_api_hooks_events.py::run_public_api_hooks_events`

        Gate:
        - `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_public_api_hooks_events()
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
