"""Cells-native marimo notebook: ch162_public_api_output_write_layout.

迁移对照:
  Before: 模块级 run_public_api_output_write_layout() 持全部逻辑;cells 薄壳
  After:  工厂选型/复杂零件装配窥视/三布局运行/事件断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch162_public_api_output_write_layout

        本章目标:
        - 演示 `OutputWriteLayout`：工厂选型 + 事件取向 + 业务格子对拍
        - 按数据形状由调用方显式调优；默认不设 `layout` 时行为与历史一致
        - `YAML` `books` / `composition` 不能设列布局

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：WriteTraceObserver / xlsx 读取 / _run_layout 助手
        2. 复杂可复用零件：`build_minimal_public_api_ir()` + `build_minimal_public_api_runtime_bindings()`
        3. **模型窥视**：渲染 `demand_ir.fields` 与 `runtime_bindings` 接线（读者无需跳库）
        4. 工厂选型：COLUMN_BUFFERED / COLUMN_CHUNKED / ROW_STREAM → 具体 sink 类型
        5. 三布局运行（.tmp/examples/ 产物）
        6. 断言：单元格一致 + 列/行事件取向 + 派生布局
        7. 汇总 chapter_result

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
    import importlib
    from pathlib import Path
    from typing import Any, Dict, List, Optional, Set, Tuple

    from openpyxl import load_workbook

    from scalim import execution as api
    from scalim.events import Event, EventType
    from scalim.ob.observer import Observer
    from scalim.planning import PlanBuilder
    from scalim.sinks import ColumnExcelSink, ExcelSink, StreamingColumnExcelSink
    from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir, build_minimal_public_api_runtime_bindings
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        ColumnExcelSink,
        Dict,
        Event,
        EventType,
        ExcelSink,
        List,
        Observer,
        Optional,
        Path,
        PlanBuilder,
        Set,
        StreamingColumnExcelSink,
        Tuple,
        api,
        build_minimal_public_api_ir,
        build_minimal_public_api_runtime_bindings,
        importlib,
        load_workbook,
        make_chapter_result,
        render_checks,
    )


@app.cell
def _(Any, Dict, Event, EventType, List, Observer, Optional, Set, Tuple, importlib, load_workbook):
    # 零件: 事件追踪 / xlsx 读取 / 运行助手
    class WriteTraceObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {
                EventType.ROW_WRITE,
                EventType.COLUMN_WRITE,
                EventType.PIPELINE_END,
            }
            self.row_field_counts: List[int] = []
            self.column_keys: List[str] = []
            self.column_row_counts: List[int] = []

        def on_event(self, event: Event) -> None:
            if event.event_type is EventType.ROW_WRITE:
                self.row_field_counts.append(int(getattr(event.payload, "field_count", 0)))
                return
            if event.event_type is EventType.COLUMN_WRITE:
                self.column_keys.append(str(getattr(event.payload, "field_key", "")))
                self.column_row_counts.append(int(getattr(event.payload, "row_count", 0)))

    def xlsx_rows(path: Path) -> List[Tuple[Any, ...]]:
        workbook = load_workbook(str(path), read_only=True, data_only=True)
        try:
            return [tuple(row) for row in workbook.active.iter_rows(values_only=True)]
        finally:
            workbook.close()

    run_ir_mod = importlib.import_module("scalim.execution.run_ir")

    def run_layout(
        *,
        demand_ir: Any,
        layout: Any,
        runtime_bindings: Any,
        path: Path,
        output_write_layout: api.OutputWriteLayout,
        streaming: bool,
    ) -> Tuple[Any, WriteTraceObserver]:
        if path.exists():
            path.unlink()
        observer = WriteTraceObserver()
        result = api.run_ir(
            demand_ir,
            api.ExecutionRequest(
                export_layout=layout,
                output=api.OutputSpec(format="excel", path=str(path), streaming=streaming, include_header=True),
                runtime_bindings=runtime_bindings,
                batch_size=10,
                output_write_layout=output_write_layout,
                components=[observer],
            ),
        )
        return result, observer

    return WriteTraceObserver, run_ir_mod, run_layout, xlsx_rows


@app.cell
def _(Path):
    base = Path(".tmp/examples/ch162_output_write_layout")
    base.mkdir(parents=True, exist_ok=True)
    return base


@app.cell
def _(
    ColumnExcelSink,
    ExcelSink,
    PlanBuilder,
    StreamingColumnExcelSink,
    api,
    base,
    build_minimal_public_api_ir,
    build_minimal_public_api_runtime_bindings,
    run_ir_mod,
):
    # ② 复杂可复用零件装配 + 工厂选型: 三种 layout -> 具体 sink 类型。
    #   - build_minimal_public_api_ir(): 最小 DemandIr（主源 items + 2 抽取字段 + 1 派生字段）。
    #   - build_minimal_public_api_runtime_bindings(): 主源 loader / 派生计算函数注入 RuntimeBindings。
    #   - PlanBuilder(demand_ir).build(): 生成执行计划;export_layout_from_demand_ir 导出写布局。
    demand_ir = build_minimal_public_api_ir()
    runtime_bindings = build_minimal_public_api_runtime_bindings()
    plan = PlanBuilder(demand_ir).build()
    layout = api.export_layout_from_demand_ir(demand_ir, plan.target_fields)

    buffered_probe = base / "probe_buffered.xlsx"
    chunked_probe = base / "probe_chunked.xlsx"
    row_probe = base / "probe_row.xlsx"
    buffered_sink = run_ir_mod._create_file_sink(
        api.OutputSpec(format="excel", path=str(buffered_probe), streaming=False),
        layout,
        output_write_layout=api.OutputWriteLayout.COLUMN_BUFFERED,
    )
    chunked_sink = run_ir_mod._create_file_sink(
        api.OutputSpec(format="excel", path=str(chunked_probe), streaming=False),
        layout,
        output_write_layout=api.OutputWriteLayout.COLUMN_CHUNKED,
    )
    row_sink = run_ir_mod._create_file_sink(
        api.OutputSpec(format="excel", path=str(row_probe), streaming=True),
        layout,
        output_write_layout=api.OutputWriteLayout.ROW_STREAM,
    )
    factory_ok = (
        isinstance(buffered_sink, ColumnExcelSink)
        and isinstance(chunked_sink, StreamingColumnExcelSink)
        and isinstance(row_sink, ExcelSink)
    )
    buffered_sink.close()
    row_sink.close()
    print("factory:", type(buffered_sink).__name__, type(chunked_sink).__name__, type(row_sink).__name__)
    return buffered_sink, chunked_sink, demand_ir, factory_ok, layout, runtime_bindings, row_sink


@app.cell(hide_code=True)
def _(demand_ir, layout, mo, runtime_bindings):
    # ③ 模型窥视：把库 fixtures builder 的装配产物直接渲染在 notebook 内，读者无需跳库。
    #   - demand_ir.fields 是 mappingproxy（键=field_id），必须用 .values() 遍历；
    #     DerivedFieldIr 可能没有 source_id，用 getattr 兜底。
    #   - layout.field_ids 即本次写出的目标字段（列布局事件的 field_key 与之一致）。
    fields_summary = [
        {
            "field_id": f.field_id,
            "name": f.name,
            "source_id": getattr(f, "source_id", "-"),
            "kind": type(f).__name__,
        }
        for f in demand_ir.fields.values()
    ]
    mo.vstack(
        [
            mo.md("**模型窥视（读者无需跳库）**——以下为最小模型的装配与接线产物："),
            mo.md(
                "字段总数 `{}`（含派生 {} 个）；layout.field_ids = {}；source_loaders = {}；derived_calculators = {}".format(
                    len(fields_summary),
                    sum(1 for f in fields_summary if f["kind"] == "DerivedFieldIr"),
                    list(layout.field_ids),
                    list(getattr(runtime_bindings, "main_source_loaders", {}).keys()),
                    list(getattr(runtime_bindings, "derived_calculators", {}).keys()),
                )
            ),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return


@app.cell
def _(api, base, demand_ir, layout, render_checks, run_layout, runtime_bindings):
    # 三布局运行
    buffered_out = base / "run_buffered.xlsx"
    chunked_out = base / "run_chunked.xlsx"
    row_out = base / "run_row.xlsx"
    buffered_result, buffered_obs = run_layout(
        demand_ir=demand_ir,
        layout=layout,
        runtime_bindings=runtime_bindings,
        path=buffered_out,
        output_write_layout=api.OutputWriteLayout.COLUMN_BUFFERED,
        streaming=False,
    )
    chunked_result, chunked_obs = run_layout(
        demand_ir=demand_ir,
        layout=layout,
        runtime_bindings=runtime_bindings,
        path=chunked_out,
        output_write_layout=api.OutputWriteLayout.COLUMN_CHUNKED,
        streaming=False,
    )
    row_result, row_obs = run_layout(
        demand_ir=demand_ir,
        layout=layout,
        runtime_bindings=runtime_bindings,
        path=row_out,
        output_write_layout=api.OutputWriteLayout.ROW_STREAM,
        streaming=True,
    )
    derived = api.resolve_output_write_layout(
        output_write_layout=None,
        streaming=False,
        output_format="excel",
        excel_column_residency=api.ExcelColumnResidency.CHUNKED,
        has_output_composition=False,
    )
    print("derived =", derived.value)
    return (
        buffered_obs,
        buffered_out,
        buffered_result,
        chunked_obs,
        chunked_out,
        chunked_result,
        derived,
        row_obs,
        row_out,
        row_result,
    )


@app.cell
def _(
    api,
    buffered_obs,
    buffered_out,
    buffered_result,
    chunked_obs,
    chunked_out,
    chunked_result,
    derived,
    factory_ok,
    layout,
    render_checks,
    row_obs,
    row_out,
    row_result,
    xlsx_rows,
):
    # 断言: 单元格一致 + 事件取向 + 派生布局
    buffered_rows = xlsx_rows(buffered_out)
    chunked_rows = xlsx_rows(chunked_out)
    expected_fields = set(layout.field_ids)
    column_events_ok = (
        not buffered_obs.row_field_counts
        and not chunked_obs.row_field_counts
        and set(buffered_obs.column_keys) == expected_fields
        and set(chunked_obs.column_keys) == expected_fields
        and buffered_obs.column_row_counts == chunked_obs.column_row_counts
        and bool(buffered_obs.column_row_counts)
        and buffered_obs.column_row_counts[0] == 3
    )
    row_events_ok = (
        len(row_obs.row_field_counts) == 3
        and not row_obs.column_keys
        and all(count == len(expected_fields) for count in row_obs.row_field_counts)
    )

    checks = {
        "工厂选型正确": factory_ok,
        "三布局 rows == 3": buffered_result.total_rows == chunked_result.total_rows == row_result.total_rows == 3,
        "buffered/chunked 产物存在": buffered_out.exists() and chunked_out.exists() and row_out.exists(),
        "单元格一致": buffered_rows == chunked_rows,
        "列布局派生 == COLUMN_CHUNKED": derived is api.OutputWriteLayout.COLUMN_CHUNKED,
        "列事件取向": column_events_ok,
        "行事件取向": row_events_ok,
        "无废弃枚举": not hasattr(api.OutputWriteLayout, "COLUMN_HOLD") and not hasattr(api.OutputWriteLayout, "COLUMN_WINDOW"),
    }
    render_checks(checks)
    return buffered_rows, checks, chunked_rows, column_events_ok, row_events_ok


@app.cell
def _(
    buffered_obs,
    buffered_out,
    buffered_result,
    buffered_rows,
    buffered_sink,
    checks,
    chunked_obs,
    chunked_out,
    chunked_result,
    chunked_rows,
    chunked_sink,
    column_events_ok,
    derived,
    factory_ok,
    make_chapter_result,
    row_obs,
    row_out,
    row_result,
    row_sink,
    row_events_ok,
):
    passed = bool(all(checks.values()))
    summary = "buffered={} chunked={} row={} factory_ok={} cells_eq={} col_ev={} row_ev={}".format(
        buffered_result.total_rows,
        chunked_result.total_rows,
        row_result.total_rows,
        factory_ok,
        buffered_rows == chunked_rows,
        column_events_ok,
        row_events_ok,
    )
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {
        "factory_ok": True,
        "rows_per_layout": 3,
        "buffered_equals_chunked": True,
        "derived_layout": "COLUMN_CHUNKED",
        "column_events_ok": True,
        "row_events_ok": True,
        "no_legacy_enums": True,
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "factory_buffered": type(buffered_sink).__name__,
            "factory_chunked": type(chunked_sink).__name__,
            "factory_row": type(row_sink).__name__,
            "buffered_rows": buffered_result.total_rows,
            "chunked_rows": chunked_result.total_rows,
            "row_stream_rows": row_result.total_rows,
            "xlsx_cells_equal": buffered_rows == chunked_rows,
            "buffered_column_writes": list(buffered_obs.column_keys),
            "chunked_column_writes": list(chunked_obs.column_keys),
            "row_write_count": len(row_obs.row_field_counts),
            "derived_from_residency_window": derived.value,
            "syntax_hint": "DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_CHUNKED)",
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
