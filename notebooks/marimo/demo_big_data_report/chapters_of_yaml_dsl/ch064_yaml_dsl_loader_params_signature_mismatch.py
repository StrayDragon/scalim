import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions
from scalim.dsl.yaml_dsl import compile as compile_yaml
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_loader_params_signature_mismatch"
_ALLOWED_MODULES = frozenset(
    [
        "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario",
        __name__,
    ]
)


def load_required_flag(flag: int, tag: str = "x") -> Mapping[int, Dict[str, object]]:
    _ = (flag, tag)
    return {}


def run_yaml_dsl_loader_params_signature_mismatch() -> ExampleResult:
    """回归: `sources.*.params` 顶层 `kwargs` 键不匹配必须编译期 `fail-fast`."""

    with tempfile.TemporaryDirectory(prefix="scalim-yaml-loader-params-") as tmpdir:
        tmp = Path(tmpdir)
        bad_unknown_yaml = tmp / "bad_params_unknown.yaml"
        bad_missing_yaml = tmp / "bad_params_missing.yaml"

        bad_unknown_yaml.write_text(
            """\
name: yaml_dsl_loader_params_signature_mismatch_unknown

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
      bad_key: 1
""",
            encoding="utf-8",
        )

        bad_missing_yaml.write_text(
            """\
name: yaml_dsl_loader_params_signature_mismatch_missing

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id}

sources:
  s1:
    loader: "notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.ch064_yaml_dsl_loader_params_signature_mismatch:load_required_flag"
    key: id
    params:
      tag: "demo"
""",
            encoding="utf-8",
        )

        unknown_msg = ""
        unknown_failed = False
        try:
            _ = compile_yaml(
                str(bad_unknown_yaml),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    runtime=DemandRunRuntimeOptions(batch_size=2),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            unknown_msg = str(exc)
            unknown_failed = bool(("sources.customers.params" in unknown_msg) and ("bad_key" in unknown_msg))

        missing_msg = ""
        missing_failed = False
        try:
            _ = compile_yaml(
                str(bad_missing_yaml),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    runtime=DemandRunRuntimeOptions(batch_size=2),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            missing_msg = str(exc)
            missing_failed = bool(("sources.s1.params" in missing_msg) and ("missing" in missing_msg or "required" in missing_msg))

        passed = bool(unknown_failed and missing_failed)
        summary = "unknown_failed={} missing_failed={}".format(unknown_failed, missing_failed)
        details: Dict[str, Any] = {
            "bad_unknown_yaml_path": str(bad_unknown_yaml),
            "bad_unknown_exc_message": unknown_msg,
            "bad_missing_yaml_path": str(bad_missing_yaml),
            "bad_missing_exc_message": missing_msg,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_loader_params_signature_mismatch()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_loader_params_signature_mismatch

        回归点:
        - `sources.*.params` 的 top-level kwargs keys 与 loader 函数签名不匹配时,必须编译期 fail-fast。
        - 仅校验 keys(不渲染 template),避免依赖 `$keys/$rows` 的执行期上下文。

        好例子 gate: `yaml_dsl_support` / `support/support_sla_report.yaml` 覆盖正常 params + $keys 注入链路。
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
    result = run_yaml_dsl_loader_params_signature_mismatch()
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
