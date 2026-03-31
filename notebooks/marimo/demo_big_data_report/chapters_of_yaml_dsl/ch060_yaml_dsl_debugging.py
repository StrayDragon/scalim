import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_debugging"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def run_yaml_dsl_debugging() -> ExampleResult:
    """一个确定性的“预期失败”章节：演示常见错误如何定位。"""
    with tempfile.TemporaryDirectory(prefix="scalim-yaml-debug-") as tmpdir:
        tmp = Path(tmpdir)
        bad_yaml = tmp / "bad_where.yaml"
        out_csv = tmp / "out.csv"

        bad_yaml.write_text(
            """\
name: yaml_dsl_debugging_bad_where
batch_size: 2

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {name: Ticket ID}

resources:
  files:
    detail_csv:
      kind: csv_file
      path: {$init_var: out_path_detail}

outputs:
  - name: detail
    to: {file: detail_csv}
    write:
      header_fields_output_by: field_id
      include_header: true
    where: "unknown_field > 0"
    fields: [ticket_id]
""",
            encoding="utf-8",
        )

        try:
            _ = compile_yaml(
                str(bad_yaml),
                allowed_modules=_ALLOWED_MODULES,
                init_vars={"out_path_detail": str(out_csv)},
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            passed = bool(("where depends on unknown fields" in msg) or ("Invalid where expression" in msg) or ("unknown fields" in msg))
            summary = "expected failure captured: {}: {}".format(type(exc).__name__, msg)
            details: Dict[str, Any] = {
                "bad_yaml_path": str(bad_yaml),
                "hint": "Fix by changing `where` to reference declared field_id(s) only.",
                "exc_type": type(exc).__name__,
                "message": msg,
            }
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=passed,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details=details,
            )

        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary="unexpected: bad YAML compiled successfully",
            details={"bad_yaml_path": str(bad_yaml)},
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_debugging()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_debugging

        ## 背景

        工程同学在改 YAML 时，最常见的痛点不是“不会写”，而是：
        - 改完以后在 CI 才发现报错
        - 错误信息不够可定位（不知道是哪个路径写错了）

        ## 需求方提问（自然语言）

        维护者：有没有一个最小例子，能演示“写错了 where/字段引用”时怎么定位？

        ## 方案选择（取舍）

        - 线上排查：成本高
        - **本章（预期失败回归）**：构造一个确定性的坏例子，在 `just examples` 里演示错误形态与定位要点

        ## 对拍点（deterministic）

        - 预期行为：`compile()` 必须失败（where 引用未知字段）
        - 断言：错误信息包含 “unknown fields/depends on unknown fields/Invalid where expression” 等可定位提示

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch060_yaml_dsl_debugging.py::run_yaml_dsl_debugging`
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
    result = run_yaml_dsl_debugging()
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
