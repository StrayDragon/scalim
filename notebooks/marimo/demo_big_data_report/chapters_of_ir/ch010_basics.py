import marimo

import time
from typing import Any, Dict, Optional, Sequence

from scalim.execution.engine import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryColumnSink
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, load_orders, set_config
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL, build_ecommerce_model, build_ecommerce_runtime_bindings
from scalim_misc.demo_big_data_report.verification import (
    OrderByVerificationResult,
    VerificationResult,
    verify_order_by,
    verify_scalim_output,
)
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")


def run_basics(
    cfg: Optional[ECommerceConfig] = None,
    *,
    targets: Optional[Sequence[str]] = None,
    batch_size: int = 10,
    row_limit: Optional[int] = None,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    prev = get_config()
    set_config(cfg)
    try:
        demand = build_ecommerce_model(cfg)
        runtime_bindings = build_ecommerce_runtime_bindings()
        targets_list = list(targets or TARGET_FIELDS_FULL)
        plan = PlanBuilder(demand).build(targets=targets_list)

        main_rows = list(load_orders())
        if row_limit is not None:
            main_rows = main_rows[: int(row_limit)]

        engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=int(batch_size))
        start = time.time()
        with InMemoryColumnSink(field_names=targets_list) as sink:
            _ = engine.run(main_rows=main_rows, sink=sink)
            results = sink.get_rows()
        elapsed = time.time() - start

        verification: VerificationResult = verify_scalim_output(results, fields_to_check=targets_list)
        order_by: OrderByVerificationResult = verify_order_by(results, ["order_id"])

        passed = bool(verification.passed and order_by.passed)
        summary = "rows={} elapsed={:.3f}s verify={} order_by={}".format(len(results), elapsed, verification.passed, order_by.passed)
        if not passed:
            summary = summary + "\n" + verification.summary + "\n" + order_by.message

        details: Dict[str, Any] = {
            "elapsed_seconds": elapsed,
            "rows": len(results),
            "plan_total_fields": plan.metadata.total_fields,
            "plan_total_sources": plan.metadata.total_sources,
            "verification": verification,
            "order_by": order_by,
        }
        return ExampleResult(
            example_id="demo_big_data_report/ch010_basics",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_basics()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch010_basics

        本章目标:
        - 走一遍最小主线：`IR → Plan → Engine → Sink`
        - 对拍(oracle)失败时可在本 notebook 里交互定位

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch010_basics.py::run_basics`

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
    cfg = build_test_config_small()
    result = run_basics(cfg=cfg, targets=TARGET_FIELDS_FULL, batch_size=10)
    return TARGET_FIELDS_FULL, cfg, result


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
