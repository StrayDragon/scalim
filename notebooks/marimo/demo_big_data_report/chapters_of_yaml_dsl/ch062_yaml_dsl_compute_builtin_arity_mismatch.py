import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, List

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions
from scalim.dsl.yaml_dsl import compile as compile_yaml
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_compute_builtin_arity_mismatch"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def run_yaml_dsl_compute_builtin_arity_mismatch() -> ExampleResult:
    """回归: `compute` 表达式中 `SAFE_FUNCTIONS` 内置函数调用形态必须编译期 `fail-fast`.

    预期:
    - `len(a, b)` / `dec(a, b)` 等 `arity mismatch` 必须在编译期失败(不进入运行期 `guardrails` 吞错语义)
    """

    with tempfile.TemporaryDirectory(prefix="scalim-yaml-compute-arity-") as tmpdir:
        tmp = Path(tmpdir)
        bad_yaml = tmp / "bad_compute.yaml"

        bad_yaml.write_text(
            """\
name: yaml_dsl_compute_builtin_arity_mismatch_bad

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id}
    group_name: {extract: category}

fields:
  _bad:
    depends_on: [ticket_id, group_name]
    # NOTE: len(...) 只接受 1 个位置参数;这里故意用 2 个参数触发 compile-time preflight。
    compute: "len(ticket_id, group_name)"
""",
            encoding="utf-8",
        )

        bad_errors: List[str] = []
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
            msg = str(exc)
            raw_errors = getattr(exc, "errors", None)
            if raw_errors:
                try:
                    bad_errors = [str(getattr(env, "message", env)) for env in raw_errors]
                except Exception:  # noqa: BLE001
                    bad_errors = [msg]
            else:
                bad_errors = [msg]
            bad_fast_failed = any(("调用形态不匹配" in m) and ("len" in m) for m in bad_errors)

        passed = bool(bad_fast_failed)
        summary = "bad_fast_failed={} errors={}".format(bad_fast_failed, len(bad_errors))
        details: Dict[str, Any] = {
            "bad_yaml_path": str(bad_yaml),
            "bad_errors": bad_errors[:10],
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_compute_builtin_arity_mismatch

        回归点: `compute` 表达式中的 SAFE_FUNCTIONS 内置函数调用形态在编译期做 arity preflight，
        避免运行期 `TypeError` 被 guardrails quiet 语义吞掉导致“结果静默错误”。

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch062_yaml_dsl_compute_builtin_arity_mismatch.py::run_yaml_dsl_compute_builtin_arity_mismatch`
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
    result = run_yaml_dsl_compute_builtin_arity_mismatch()
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
