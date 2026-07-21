"""Cells-native: ch040_sinks — multiple sink types and output shapes."""
import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Sinks: Row, Column, CSV, Pandas

演示 InMemoryRowDataSink / InMemoryColumnSink / CSVSink / ColumnCSVSink 的输出形态与对拍。
构建 IR model 一次，传给不同 sink 引擎实例。""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path
    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    import tempfile
    from pathlib import Path
    from typing import Dict, List, Tuple, cast

    from scalim.execution.engine import ScalimEngine
    from scalim.planning import PlanBuilder
    from scalim.sinks import ColumnCSVSink, CSVSink
    from scalim.sinks.memory import InMemoryColumnSink, InMemoryRowDataSink
    from scalim.typedefs import RowData
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import (
        compare_csv_files,
        export_to_csv,
        python_build_order_report,
        verify_scalim_output,
    )
    return (
        ColumnCSVSink, CSVSink, Dict, InMemoryColumnSink, InMemoryRowDataSink,
        Path, PlanBuilder, RowData, ScalimEngine, TARGET_FIELDS_FULL,
        build_ecommerce_model, build_ecommerce_runtime_bindings, build_test_config_small,
        cast, compare_csv_files, export_to_csv, python_build_order_report, tempfile, verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL[:12])
    print("cfg built, {} targets".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    """Build IR model, plan, and runtime bindings once — shared by all sinks."""
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=targets)
    print("demand.fields={} plan.total_sources={}".format(len(demand.fields), plan.metadata.total_sources))
    return demand, plan, runtime_bindings


@app.cell
def _(InMemoryColumnSink, InMemoryRowDataSink, ScalimEngine, demand, plan, runtime_bindings, targets, verify_scalim_output):
    """RowDataSink vs ColumnSink — compare both outputs."""
    e1 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
    with InMemoryRowDataSink() as row_sink:
        e1.run(main_rows=None, sink=row_sink)
        row_results = row_sink.get_data()

    e2 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
    with InMemoryColumnSink(field_names=targets) as col_sink:
        e2.run(main_rows=None, sink=col_sink)
        col_results = col_sink.get_rows()

    vr_row = verify_scalim_output(row_results, fields_to_check=targets)
    vr_col = verify_scalim_output(col_results, fields_to_check=targets)
    print("row={} verify={}  col={} verify={}".format(len(row_results), vr_row.passed, len(col_results), vr_col.passed))
    return col_results, row_results, vr_col, vr_row


@app.cell
def _(
    ColumnCSVSink, CSVSink, ScalimEngine, Path,
    col_results, compare_csv_files, export_to_csv, python_build_order_report,
    demand, plan, runtime_bindings, targets, tempfile,
):
    """CSV outputs: oracle comparison + real CSVSink/ColumnCSVSink files."""
    py_results = python_build_order_report(targets)
    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        scalim_csv = tp / "scalim.csv"
        python_csv = tp / "python.csv"
        export_to_csv(col_results, str(scalim_csv), targets)
        export_to_csv(py_results, str(python_csv), targets)
        csv_matched, csv_diff = compare_csv_files(str(scalim_csv), str(python_csv))

        csv_row_path = tp / "row_sink.csv"
        er = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with CSVSink(str(csv_row_path), field_names=targets) as rs:
            er.run(main_rows=None, sink=rs)

        csv_col_path = tp / "col_sink.csv"
        ec = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with ColumnCSVSink(str(csv_col_path), field_names=targets) as cs:
            ec.run(main_rows=None, sink=cs)

        with csv_row_path.open(encoding="utf-8") as fr:
            row_lines = sum(1 for _ in fr) - 1
        with csv_col_path.open(encoding="utf-8") as fc:
            col_lines = sum(1 for _ in fc) - 1
        print("csv_match={}  row_lines={}  col_lines={}".format(csv_matched, row_lines, col_lines))
    return col_lines, csv_diff, csv_matched, row_lines


@app.cell
def _(col_results, targets, verify_scalim_output):
    """Optional pandas round-trip."""
    available = False
    vr_pd = None
    try:
        import pandas as pd
        df = pd.DataFrame(col_results)
        pd_rows = df[list(targets)].to_dict(orient="records")
        vr_pd = verify_scalim_output(pd_rows, fields_to_check=targets)
        available = True
        print("pandas: available, verify={}".format(vr_pd.passed))
    except ImportError:
        print("pandas: not available (skipped)")
    return available, vr_pd


@app.cell
def _(available, col_lines, col_results, csv_matched, row_lines, vr_col, vr_pd, vr_row):
    passed = bool(vr_row.passed and vr_col.passed and csv_matched
                  and row_lines == len(col_results) and col_lines == len(col_results))
    if available and vr_pd:
        passed = passed and vr_pd.passed

    summary = "rows={} verify_row={} verify_col={} csv_match={} csv_sinks={}/{}".format(
        len(col_results), vr_row.passed, vr_col.passed, csv_matched, row_lines, col_lines)
    if not csv_matched:
        summary = summary + "\n" + (csv_diff or "(csv diff unavailable)")

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {"rows": len(col_results), "verify_row": vr_row, "verify_col": vr_col,
                    "csv_matched": csv_matched, "pandas_available": available},
    }
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
        kind="success" if ok else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows
    detail_rows = details_to_rows(chapter_result["details"])
    if detail_rows:
        mo.ui.table(detail_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
