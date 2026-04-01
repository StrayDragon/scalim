import marimo

import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict

from scalim.dsl.by_yaml import run
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
from scalim.sinks import InMemoryRowSink
from scalim_misc.demo_big_data_report.by_yaml_dsl import loader_retry_demo_mod as demo_mod
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")


def run_loader_retry() -> ExampleResult:
    demand_yaml = textwrap.dedent(
        """
        name: loader_retry_demo

        main_source:
          source_id: orders
          loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              {}
        """
    ).lstrip()

    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod"])

    with tempfile.TemporaryDirectory() as tmpdir:
        demand_path = Path(tmpdir) / "demand.yaml"
        demand_path.write_text(demand_yaml, encoding="utf-8")

        # 1) 不启用 `retry`: 第一次失败直接抛错
        demo_mod.reset()
        sink_no_retry = InMemoryRowSink()
        no_retry_ok = False
        try:
            _ = run(str(demand_path), allowed_modules=allowed_modules, sink=sink_no_retry)
        except demo_mod.TransientError:
            no_retry_ok = True

        # 2) 启用 `retry`: 通过运行时注入(`loader_retry=...`)自动重试后成功
        demo_mod.reset()
        sink_with_retry = InMemoryRowSink()
        injected_retry = LoaderRetryPoliciesSpec(
            default=LoaderRetryPolicySpec(
                enabled=True,
                should_retry=demo_mod.should_retry,
                max_attempts=2,
                max_elapsed_seconds=5.0,
                backoff="fixed",
                base_delay_seconds=0.0,
                max_delay_seconds=0.0,
                jitter=False,
            )
        )
        _ = run(
            str(demand_path),
            allowed_modules=allowed_modules,
            sink=sink_with_retry,
            loader_retry=injected_retry,
        )
        expected_call_count = 2
        with_retry_ok = sink_with_retry.get_data() == [{"order_id": 1}] and demo_mod.get_call_count() == expected_call_count

    passed = bool(no_retry_ok and with_retry_ok)
    summary = "no_retry_ok={} with_retry_ok={}".format(no_retry_ok, with_retry_ok)
    details: Dict[str, Any] = {"call_count": demo_mod.get_call_count()}
    return ExampleResult(
        example_id="demo_big_data_report/ch100_loader_retry",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_loader_retry()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch100_loader_retry

        本章目标:
        - 演示 YAML DSL 的 loader retry 策略：不开启则失败/开启后可恢复

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch100_loader_retry.py::run_loader_retry`

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
    result = run_loader_retry()
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
