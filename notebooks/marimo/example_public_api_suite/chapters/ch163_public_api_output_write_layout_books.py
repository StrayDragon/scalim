"""Cells-native marimo notebook: ch163_public_api_output_write_layout_books.

迁移对照:
  Before: 模块级 run_public_api_output_write_layout_books() 持全部逻辑;cells 薄壳
  After:  四场景 fail-fast 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch163_public_api_output_write_layout_books

        本章目标:
        - YAML books / `output_composition` 不能设 `COLUMN_CHUNKED` / `COLUMN_BUFFERED`
        - `ExcelColumnResidency.CHUNKED` 同样 fail-fast（禁止假开关）
        - YAML 声明 `output_write_layout` 字段在入口即拒绝
        - fail-fast 发生在 pipeline 启动前（无 `PIPELINE_START`）

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：PipelineTraceObserver / run_books / caught_message
        2. 场景 A/B/C：COLUMN_CHUNKED / COLUMN_BUFFERED / residency 均预期 fail-fast
        3. 场景 D：YAML `output_write_layout` 字段入口拒绝
        4. 断言展开 → chapter_result

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
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, FrozenSet, List, Optional, Set

    ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])

    from scalim.dsl import yaml_dsl as api
    from scalim.events import Event, EventType
    from scalim.ob.observer import Observer
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        ALLOWED_MODULES,
        Any,
        Dict,
        Event,
        EventType,
        FrozenSet,
        List,
        Observer,
        Optional,
        Path,
        Set,
        api,
        make_chapter_result,
        render_checks,
        tempfile,
    )


@app.cell
def _(ALLOWED_MODULES, Any, Dict, Event, EventType, List, Observer, Optional, Path, Set):
    # 零件: pipeline 事件追踪 / 文本写入 / books demand yaml / 运行助手 / 错误摘要
    class PipelineTraceObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.PIPELINE_START, EventType.PIPELINE_END}
            self.seen: List[EventType] = []

        def on_event(self, event: Event) -> None:
            event_type = getattr(event, "event_type", None)
            if isinstance(event_type, EventType):
                self.seen.append(event_type)

    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    def books_demand_yaml() -> str:
        return "\n".join(
            [
                "name: public_api_layout_books",
                "",
                "main_source:",
                "  source_id: items",
                '  loader: "scalim_misc.examples.public_api._fixtures:load_items"',
                "  fields:",
                "    item_id: {extract: item_id, name: Item ID}",
                "    dim_id: {extract: dim_id, name: Dim ID}",
                "",
                "sources: {}",
            ]
        )

    def run_books(*, demand_path: Path, output_root: Path, runtime: api.DemandRunRuntimeOptions) -> None:
        overrides = api.RunOverrides(
            outputs=(
                api.OutputOverride(
                    name="detail_book",
                    fields=("item_id", "dim_id"),
                    to=api.OutputToOverride(sheet="Detail"),
                    write=api.OutputWriteOverride(include_header=True, header_fields_output_by="field_id"),
                ),
            ),
            resources=api.ResourcesOverride(
                books={"report": api.BookResourceOverride(path=output_root, allow_formulas=False)},
            ),
            outputs_defaults=api.OutputsDefaultsOverride(to=api.OutputDefaultsToOverride(book="report")),
        )
        _ = api.run(
            str(demand_path),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=runtime,
                outputs=api.DemandRunOutputOptions(overrides=overrides),
            ),
        )

    def caught_message(exc: BaseException) -> str:
        parts = ["{}: {}".format(type(exc).__name__, exc)]
        errors = getattr(exc, "errors", None)
        if errors:
            extra = "\n".join(str(getattr(item, "message", item)) for item in errors)
            if extra:
                parts.append(extra)
        return "\n".join(parts)

    return PipelineTraceObserver, books_demand_yaml, caught_message, run_books, write_text


@app.cell
def _(ALLOWED_MODULES, Path, api, books_demand_yaml, tempfile, write_text):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-public-api-layout-books-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    demand_path = tmp / "demand.yaml"
    write_text(demand_path, books_demand_yaml())
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, demand_path, tmp


@app.cell
def _(PipelineTraceObserver, api, caught_message, demand_path, run_books, tmp):
    # 场景 A/B/C: 三种列布局开关对 books/composition 均 fail-fast
    chunked_obs = PipelineTraceObserver()
    buffered_obs = PipelineTraceObserver()
    residency_obs = PipelineTraceObserver()
    chunked_err = ""
    buffered_err = ""
    residency_err = ""

    try:
        run_books(
            demand_path=demand_path,
            output_root=tmp / "chunked",
            runtime=api.DemandRunRuntimeOptions(
                batch_size=10,
                output_write_layout=api.OutputWriteLayout.COLUMN_CHUNKED,
                components=[chunked_obs],
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常
        chunked_err = caught_message(exc)

    try:
        run_books(
            demand_path=demand_path,
            output_root=tmp / "buffered",
            runtime=api.DemandRunRuntimeOptions(
                batch_size=10,
                output_write_layout=api.OutputWriteLayout.COLUMN_BUFFERED,
                components=[buffered_obs],
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常
        buffered_err = caught_message(exc)

    try:
        run_books(
            demand_path=demand_path,
            output_root=tmp / "residency",
            runtime=api.DemandRunRuntimeOptions(
                batch_size=10,
                excel_column_residency=api.ExcelColumnResidency.CHUNKED,
                components=[residency_obs],
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常
        residency_err = caught_message(exc)

    return buffered_err, buffered_obs, chunked_err, chunked_obs, residency_err, residency_obs


@app.cell
def _(ALLOWED_MODULES, api, books_demand_yaml, caught_message, demand_path, tmp, write_text):
    # 场景 D: YAML 声明 output_write_layout 字段入口拒绝
    illegal_yaml = tmp / "illegal_layout.yaml"
    write_text(illegal_yaml, books_demand_yaml() + "\noutput_write_layout: column_chunked\n")
    yaml_field_err = ""
    try:
        _ = api.run(
            str(illegal_yaml),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=api.DemandRunRuntimeOptions(batch_size=10),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常
        yaml_field_err = caught_message(exc)
    print("yaml_field_err has output_write_layout:", "output_write_layout" in yaml_field_err)
    return yaml_field_err


@app.cell
def _(EventType, buffered_err, buffered_obs, chunked_err, chunked_obs, render_checks, residency_err, residency_obs, yaml_field_err):
    chunked_ok = "output_composition" in chunked_err and EventType.PIPELINE_START not in chunked_obs.seen
    buffered_ok = "output_composition" in buffered_err and EventType.PIPELINE_START not in buffered_obs.seen
    residency_ok = "output_composition" in residency_err and EventType.PIPELINE_START not in residency_obs.seen
    yaml_ok = "output_write_layout" in yaml_field_err and "OutputWriteLayout" in yaml_field_err
    checks = {
        "COLUMN_CHUNKED fail-fast": chunked_ok,
        "COLUMN_BUFFERED fail-fast": buffered_ok,
        "residency fail-fast": residency_ok,
        "YAML output_write_layout 入口拒绝": yaml_ok,
    }
    render_checks(checks)
    return checks, chunked_ok, buffered_ok, residency_ok, yaml_ok


@app.cell
def _(buffered_err, buffered_obs, checks, chunked_err, chunked_obs, make_chapter_result, residency_err, residency_obs, yaml_field_err):
    passed = bool(all(checks.values()))
    summary = "chunked_ok={} buffered_ok={} residency_ok={} yaml_ok={}".format(
        "output_composition" in chunked_err,
        "output_composition" in buffered_err,
        "output_composition" in residency_err,
        "output_write_layout" in yaml_field_err,
    )
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {
        "column_chunked_fail_fast": True,
        "column_buffered_fail_fast": True,
        "residency_fail_fast": True,
        "yaml_entry_rejected": True,
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "chunked_err": chunked_err,
            "buffered_err": buffered_err,
            "residency_err": residency_err,
            "yaml_field_err": yaml_field_err,
            "chunked_pipeline_events": [str(item) for item in chunked_obs.seen],
            "buffered_pipeline_events": [str(item) for item in buffered_obs.seen],
            "residency_pipeline_events": [str(item) for item in residency_obs.seen],
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
