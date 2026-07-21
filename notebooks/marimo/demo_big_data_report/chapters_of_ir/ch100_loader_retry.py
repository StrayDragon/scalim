"""Cells-native: ch100_loader_retry — YAML DSL loader retry policy."""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Loader Retry: YAML DSL 运行时重试

演示 DemandRunRuntimeOptions.loader_retry 策略：不开启则失败，开启后自动重试成功。""")
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
    import textwrap
    from pathlib import Path
    from typing import Dict

    from scalim.dsl.yaml_dsl import (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        run,
    )
    from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
    from scalim_misc.demo_big_data_report.by_yaml_dsl import loader_retry_demo_mod as demo_mod

    return (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        Dict,
        LoaderRetryPoliciesSpec,
        LoaderRetryPolicySpec,
        Path,
        demo_mod,
        run,
        tempfile,
        textwrap,
    )


@app.cell
def _(Path, demo_mod, tempfile, textwrap):
    """Write demand YAML and prepare test fixtures."""
    demand_yaml = textwrap.dedent("""
        name: loader_retry_demo
        main_source:
          source_id: orders
          loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              {}
    """).lstrip()
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod"])
    print("demand YAML prepared, allowed_modules OK")
    return allowed_modules, demand_yaml


@app.cell
def _(
    CaptureRows,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    LoaderRetryPoliciesSpec,
    LoaderRetryPolicySpec,
    Path,
    allowed_modules,
    demand_yaml,
    demo_mod,
    run,
    tempfile,
):
    """Run: no-retry (expects failure) and with-retry (expects success)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        demand_path = Path(tmpdir) / "demand.yaml"
        demand_path.write_text(demand_yaml, encoding="utf-8")

        # 1) No retry: should fail
        demo_mod.reset()
        no_retry_ok = False
        try:
            run(str(demand_path), options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=allowed_modules)))
        except demo_mod.TransientError:
            no_retry_ok = True

        # 2) With retry: should succeed after retry
        demo_mod.reset()
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
        result = run(
            str(demand_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
                runtime=DemandRunRuntimeOptions(loader_retry=injected_retry),
                outputs=DemandRunOutputOptions(capture=CaptureRows()),
            ),
        )
        captured = result.captured_rows
        captured_rows = [] if captured is None else list(captured.iter_row_data())
        with_retry_ok = captured_rows == [{"order_id": 1}] and demo_mod.get_call_count() == 2

    print("no_retry_ok={} with_retry_ok={} call_count={}".format(no_retry_ok, with_retry_ok, demo_mod.get_call_count()))
    return no_retry_ok, with_retry_ok


@app.cell
def _(demo_mod, no_retry_ok, with_retry_ok):
    passed = bool(no_retry_ok and with_retry_ok)
    summary = "no_retry_ok={} with_retry_ok={}".format(no_retry_ok, with_retry_ok)

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {"call_count": demo_mod.get_call_count()},
    }
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])), kind="success" if ok else "danger")
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
