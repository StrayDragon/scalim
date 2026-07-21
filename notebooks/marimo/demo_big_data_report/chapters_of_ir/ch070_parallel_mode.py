"""Cells-native: ch070_parallel_mode — sequential vs adaptive parallel execution."""
import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Parallel Mode: seq vs adaptive

对比两种 parallel_mode 下的输出一致性和行数。""")
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
    from typing import Dict, List, Sequence

    from scalim.execution.engine import ScalimEngine
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink
    from scalim.typedefs import RowData
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output
    return (
        Dict, InMemoryColumnSink, List, PlanBuilder, RowData, ScalimEngine, Sequence,
        TARGET_FIELDS_FULL, build_ecommerce_model, build_ecommerce_runtime_bindings,
        build_test_config_small, verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL[:12])
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=targets)
    return demand, plan, runtime_bindings


@app.cell
def _(InMemoryColumnSink, ScalimEngine, demand, plan, runtime_bindings, targets, verify_scalim_output):
    """Run seq and adaptive, compare outputs."""
    e_seq = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10, parallel_mode="seq")
    with InMemoryColumnSink(field_names=targets) as sink_seq:
        e_seq.run(main_rows=None, sink=sink_seq)
        rows_seq = sink_seq.get_rows()

    e_adp = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10, parallel_mode="adaptive")
    with InMemoryColumnSink(field_names=targets) as sink_adp:
        e_adp.run(main_rows=None, sink=sink_adp)
        rows_adp = sink_adp.get_rows()

    vr_seq = verify_scalim_output(rows_seq, fields_to_check=targets)
    vr_adp = verify_scalim_output(rows_adp, fields_to_check=targets)
    print("seq: {} rows verify={}  adaptive: {} rows verify={}".format(len(rows_seq), vr_seq.passed, len(rows_adp), vr_adp.passed))
    return rows_seq, vr_adp, vr_seq


@app.cell
def _(rows_seq, vr_adp, vr_seq):
    passed = bool(vr_seq.passed and vr_adp.passed and len(rows_seq) > 0)
    summary = "rows={} verify_seq={} verify_adaptive={}".format(len(rows_seq), vr_seq.passed, vr_adp.passed)

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {"rows": len(rows_seq), "verify_seq": vr_seq, "verify_adaptive": vr_adp},
    }
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
               kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows
    d_rows = details_to_rows(chapter_result["details"])
    if d_rows:
        mo.ui.table(d_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
