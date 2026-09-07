"""Cells-native marimo notebook: ch180_public_api_hooks_events.

迁移对照:
  Before: 模块级 run_public_api_hooks_events() 持全部逻辑;cells 薄壳
  After:  Hook/Observer 零件、运行、事件断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch180_public_api_hooks_events

        本章目标:
        - Hook(`on_pipeline_start/end/loader_call`)与 Observer 双视角收事件
        - 最小 run_ir 闭环（内存 sink）

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：CounterHook（统计）+ TraceObserver（事件序列）
        2. `ExecutionRequest`（双组件注入）→ `run_ir` → 内存 sink
        3. 断言：行数 + hook 统计 + observer 事件计数
        4. 汇总 chapter_result

        Gate: `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from dataclasses import dataclass, field
    from typing import Any, Dict, List, Optional, Set

    from scalim.events import Event, EventType
    from scalim.execution import ExecutionRequest, OutputSpec, export_layout_from_demand_ir, run_ir
    from scalim.hooks import BaseHook
    from scalim.ob.observer import Observer
    from scalim.sinks.memory import InMemoryRowDataSink
    from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir, build_minimal_public_api_runtime_bindings
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        BaseHook,
        Dict,
        Event,
        EventType,
        ExecutionRequest,
        InMemoryRowDataSink,
        List,
        Observer,
        Optional,
        OutputSpec,
        Set,
        build_minimal_public_api_ir,
        build_minimal_public_api_runtime_bindings,
        dataclass,
        export_layout_from_demand_ir,
        field,
        make_chapter_result,
        render_checks,
        run_ir,
    )


@app.cell
def _(Any, BaseHook, Dict, Event, EventType, List, Observer, Optional, Set, dataclass, field):
    # 零件: Hook 统计 + Observer 事件序列
    @dataclass
    class HookStats:
        pipeline_start: int = 0
        pipeline_end: int = 0
        loader_calls: List[str] = field(default_factory=list)

    class CounterHook(BaseHook):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {
                EventType.PIPELINE_START,
                EventType.PIPELINE_END,
                EventType.LOADER_CALL,
            }
            self.stats = HookStats()

        def on_pipeline_start(self, event: Event) -> None:
            _ = event
            self.stats.pipeline_start += 1

        def on_pipeline_end(self, event: Event) -> None:
            _ = event
            self.stats.pipeline_end += 1

        def on_loader_call(self, event: Event) -> None:
            payload = event.payload
            loader_name = getattr(payload, "loader_name", None)
            if loader_name:
                self.stats.loader_calls.append(str(loader_name))

    class TraceObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {
                EventType.PIPELINE_START,
                EventType.PIPELINE_END,
                EventType.LOADER_CALL,
            }
            self.seen_event_types: List[EventType] = []

        def on_event(self, event: Any) -> None:
            event_type = getattr(event, "event_type", None)
            if isinstance(event_type, EventType):
                self.seen_event_types.append(event_type)

    return CounterHook, HookStats, TraceObserver


@app.cell
def _(
    CounterHook,
    ExecutionRequest,
    InMemoryRowDataSink,
    OutputSpec,
    TraceObserver,
    build_minimal_public_api_ir,
    build_minimal_public_api_runtime_bindings,
    export_layout_from_demand_ir,
    run_ir,
):
    hook = CounterHook()
    observer = TraceObserver()

    demand_ir = build_minimal_public_api_ir()
    runtime_bindings = build_minimal_public_api_runtime_bindings()
    export_layout = export_layout_from_demand_ir(
        demand_ir,
        ("item_id", "dim_id", "value_plus_one"),
        header_fields_output_by="field_id",
    )

    sink = InMemoryRowDataSink()
    request = ExecutionRequest(
        export_layout=export_layout,
        output=OutputSpec(path=None),
        sink=sink,
        output_composition=None,
        observability=None,
        guardrails=None,
        loader_retry=None,
        runtime_bindings=runtime_bindings,
        components=[observer, hook],
        batch_size=10,
        parallel_mode="seq",
        max_workers=0,
    )
    core = run_ir(demand_ir, request)
    rows = sink.get_data()
    print("rows =", len(rows))
    return core, demand_ir, hook, observer, request, rows, runtime_bindings, sink


@app.cell
def _(EventType, core, hook, observer, render_checks, rows):
    checks = {
        "rows == 3": core.total_rows == len(rows) == 3,
        "首行 value_plus_one == 2": bool(rows) and rows[0].get("value_plus_one") == 2,
        "hook pipeline_start == 1": hook.stats.pipeline_start == 1,
        "hook pipeline_end == 1": hook.stats.pipeline_end == 1,
        "hook loader_calls == [items]": hook.stats.loader_calls == ["items"],
        "observer 三事件各 1 次": (
            observer.seen_event_types.count(EventType.PIPELINE_START) == 1
            and observer.seen_event_types.count(EventType.PIPELINE_END) == 1
            and observer.seen_event_types.count(EventType.LOADER_CALL) == 1
        ),
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, hook, make_chapter_result, observer, rows):
    passed = bool(all(checks.values()))
    summary = "rows={} hook(pipeline_start={}, pipeline_end={}, loader_calls={}) observer_events={}".format(
        len(rows),
        hook.stats.pipeline_start,
        hook.stats.pipeline_end,
        len(hook.stats.loader_calls),
        len(observer.seen_event_types),
    )
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {
        "rows": 3,
        "first_value_plus_one": 2,
        "hook_pipeline_start": 1,
        "hook_pipeline_end": 1,
        "hook_loader_calls": ["items"],
        "observer_events_each_once": True,
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "event_types": [str(x) for x in observer.seen_event_types],
            "hook": {
                "pipeline_start": hook.stats.pipeline_start,
                "pipeline_end": hook.stats.pipeline_end,
                "loader_calls": list(hook.stats.loader_calls),
            },
            "rows": rows,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
