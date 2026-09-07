"""Cells-native marimo notebook: ch170_public_api_ob.

迁移对照:
  Before: 模块级 run_public_api_ob() 持全部逻辑;cells 薄壳
  After:  ob smoke 闭环在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch170_public_api_ob

        本章目标:
        - `scalim.ob` facade smoke：`Observability().build_manager(CAPTURE)` 手动
          emit pipeline_start / pipeline_end 并 drain 事件

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 触达 `scalim.ob` 的 public `__all__`
        2. `build_manager(CAPTURE)` → emit 两个事件
        3. 断言：事件序列 == [PIPELINE_START, PIPELINE_END]
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
    from typing import Any, Dict

    from scalim.events import EventType
    from scalim import ob as api
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, EventType, api, make_chapter_result, render_checks


@app.cell
def _(EventType, api, render_checks):
    symbols = {name: getattr(api, name) for name in api.__all__}
    ob = api.Observability()
    manager = ob.build_manager(mode=api.ObserverManagerMode.CAPTURE)
    manager.emit_pipeline_start(targets=["item_id"], batch_size=2)
    manager.emit_pipeline_end(total_batches=1, total_duration=0.01)

    events = manager.drain_events()
    print("events =", [e.event_type for e in events])
    return events, manager, ob, symbols


@app.cell
def _(EventType, events, render_checks):
    checks = {
        "事件序列 == [PIPELINE_START, PIPELINE_END]": [e.event_type for e in events] == [EventType.PIPELINE_START, EventType.PIPELINE_END],
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, make_chapter_result, symbols, events):
    passed = bool(all(checks.values()))
    summary = "events={} types={}".format(len(events), ",".join(e.event_type for e in events))
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "event_types": [e.event_type for e in events],
            "symbols_count": len(symbols),
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
