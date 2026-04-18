import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions
from scalim.dsl.yaml_dsl import compile as compile_yaml
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_should_retry_signature_mismatch"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def run_yaml_dsl_should_retry_signature_mismatch() -> ExampleResult:
    """回归: `should_retry(exc, ctx)` 签名不匹配必须编译期 `fail-fast`."""

    def bad_should_retry(*, exc: Exception, ctx: object) -> bool:  # type: ignore[no-untyped-def]
        _ = (exc, ctx)
        return True

    with tempfile.TemporaryDirectory(prefix="scalim-yaml-should-retry-") as tmpdir:
        tmp = Path(tmpdir)
        yaml_path = tmp / "bad_should_retry.yaml"
        yaml_path.write_text(
            """\
name: yaml_dsl_should_retry_signature_mismatch_bad

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id}
""",
            encoding="utf-8",
        )

        exc_msg = ""
        bad_fast_failed = False
        try:
            _ = compile_yaml(
                str(yaml_path),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    runtime=DemandRunRuntimeOptions(
                        batch_size=2,
                        loader_retry=LoaderRetryPoliciesSpec(
                            default=LoaderRetryPolicySpec(enabled=True, should_retry=bad_should_retry, max_attempts=2)
                        ),
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            exc_msg = str(exc)
            bad_fast_failed = bool(("loader_retry.default.should_retry" in exc_msg) and ("函数签名不匹配" in exc_msg))

        passed = bool(bad_fast_failed)
        summary = "bad_fast_failed={}".format(bad_fast_failed)
        details: Dict[str, Any] = {
            "bad_yaml_path": str(yaml_path),
            "bad_exc_message": exc_msg,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_should_retry_signature_mismatch()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_should_retry_signature_mismatch

        回归点:
        - retry policy enabled 时,`should_retry(exc, ctx)` 的签名不匹配必须编译期 fail-fast,
          避免运行期 `_safe_should_retry` 将 TypeError 静默降级为 False。

        好例子 gate: `yaml_dsl_ads` chapter 运行时注入 retry policy,并断言 retry_calls==2。
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
    result = run_yaml_dsl_should_retry_signature_mismatch()
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
