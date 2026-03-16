import marimo

from typing import Any, Dict, List, Optional, Sequence

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryColumnSink
from scalim.typedefs import RowData
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL, build_ecommerce_model
from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")


def _run(cfg: ECommerceConfig, targets: Sequence[str], *, parallel_mode: str, batch_size: int) -> List[RowData]:
    set_config(cfg)
    demand = build_ecommerce_model(cfg)
    plan = PlanBuilder(demand).build(targets=list(targets))
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size), parallel_mode=parallel_mode)
    with InMemoryColumnSink(field_names=list(targets)) as sink:
        _ = engine.run(main_rows=None, sink=sink)
        rows: List[RowData] = sink.get_rows()
        return rows


def run_parallel_mode(
    cfg: Optional[ECommerceConfig] = None,
    *,
    targets: Optional[Sequence[str]] = None,
    batch_size: int = 10,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    prev = get_config()
    set_config(cfg)
    try:
        targets_list = list(targets or TARGET_FIELDS_FULL[:12])
        rows_seq = _run(cfg, targets_list, parallel_mode="seq", batch_size=batch_size)
        rows_adaptive = _run(cfg, targets_list, parallel_mode="adaptive", batch_size=batch_size)

        vr_seq: VerificationResult = verify_scalim_output(rows_seq, fields_to_check=targets_list)
        vr_adaptive: VerificationResult = verify_scalim_output(rows_adaptive, fields_to_check=targets_list)

        passed = bool(vr_seq.passed and vr_adaptive.passed and len(rows_seq) == len(rows_adaptive))
        summary = "rows={} verify_seq={} verify_adaptive={}".format(len(rows_seq), vr_seq.passed, vr_adaptive.passed)
        if not vr_seq.passed:
            summary = summary + "\nseq: " + vr_seq.summary
        if not vr_adaptive.passed:
            summary = summary + "\nadaptive: " + vr_adaptive.summary

        details: Dict[str, Any] = {
            "rows": len(rows_seq),
            "verify_seq": vr_seq,
            "verify_adaptive": vr_adaptive,
        }
        return ExampleResult(
            example_id="demo_big_data_report/parallel_mode",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_parallel_mode()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / parallel_mode

        本章目标:
        - 演示并行执行相关配置与行为的最小回归入口

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/parallel_mode.py::run_parallel_mode`

        Gate:
        - `just examples`（跑全量）
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

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _():
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL

    cfg = build_test_config_small()
    targets = TARGET_FIELDS_FULL[:12]
    result = run_parallel_mode(cfg, targets=targets, batch_size=10)
    return TARGET_FIELDS_FULL, cfg, result, targets


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
