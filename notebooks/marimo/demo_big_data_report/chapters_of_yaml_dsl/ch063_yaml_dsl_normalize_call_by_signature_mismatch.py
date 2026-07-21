import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions
from scalim.dsl.yaml_dsl import compile as compile_yaml
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_normalize_call_by_signature_mismatch"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def run_yaml_dsl_normalize_call_by_signature_mismatch() -> ExampleResult:
    """回归: `sources.*.normalize.call_by` 签名不匹配必须编译期 `fail-fast`."""

    with tempfile.TemporaryDirectory(prefix="scalim-yaml-normalize-call-by-") as tmpdir:
        tmp = Path(tmpdir)
        bad_yaml = tmp / "bad_normalize_call_by.yaml"

        bad_yaml.write_text(
            """\
name: yaml_dsl_normalize_call_by_signature_mismatch_bad

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id}

sources:
  customers:
    loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_customers"
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    normalize:
      # NOTE: normalize_kwonly_result(*, result) 不接受任何位置参数,必须编译期 fast-fail。
      call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:normalize_kwonly_result"
      index_by_key: {}
""",
            encoding="utf-8",
        )

        bad_exc_msg = ""
        bad_fast_failed = False
        try:
            _ = compile_yaml(
                str(bad_yaml),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    runtime=DemandRunRuntimeOptions(batch_size=2),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            bad_exc_msg = str(exc)
            bad_fast_failed = bool(
                ("sources.customers.normalize.call_by" in bad_exc_msg)
                and ("函数签名不匹配" in bad_exc_msg)
                and ("normalize.call_by(result" in bad_exc_msg)
            )

        passed = bool(bad_fast_failed)
        summary = "bad_fast_failed={}".format(bad_fast_failed)
        details: Dict[str, Any] = {
            "bad_yaml_path": str(bad_yaml),
            "bad_exc_message": bad_exc_msg,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter():
    """SSOT entry: headless runner / pytest import this."""
    outputs, defs = app.run()
    return defs["chapter_result"]


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_normalize_call_by_signature_mismatch

        回归点: `sources.*.normalize.call_by` 的签名不满足 `(result)`/`(result, ctx)` 合约时，
        必须在编译期 fail-fast（不进入运行期）。

        好例子 gate: `support/support_sla_report.yaml` 已注入 identity normalize.call_by，
        并由 `yaml_dsl_support` chapter 对拍 oracle 兜底。
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

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_yaml_dsl_normalize_call_by_signature_mismatch()
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
