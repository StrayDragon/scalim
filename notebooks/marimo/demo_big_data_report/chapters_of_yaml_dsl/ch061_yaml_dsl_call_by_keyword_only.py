import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
from scalim.dsl.yaml_dsl import compile as compile_yaml
from scalim.execution import run_ir
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_call_by_keyword_only"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def run_yaml_dsl_call_by_keyword_only() -> ExampleResult:
    """回归: call_by 位置参数不应“绕过” `keyword-only` 签名.

    预期:
    - `call_by: "...:is_valid_group(group_name)"` 必须在编译期 `fast-fail`
    - `call_by: "...:is_valid_group(group_name=group_name)"` 可正常运行
    """

    with tempfile.TemporaryDirectory(prefix="scalim-yaml-call-by-kwonly-") as tmpdir:
        tmp = Path(tmpdir)
        bad_yaml = tmp / "bad_call_by.yaml"
        good_yaml = tmp / "good_call_by.yaml"
        out_root = tmp / "out"

        init_vars: Dict[str, object] = {"out_root": str(out_root)}

        bad_yaml.write_text(
            """\
name: yaml_dsl_call_by_keyword_only_bad

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id, name: 工单ID, value_cast: int}
    group_name: {extract: category, name: 分组名}

fields:
  _is_valid_group:
    name: 是否合法分组
    # NOTE: `is_valid_group(*, group_name, **kw)` 是 keyword-only; 这里故意用位置参数触发错误。
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:is_valid_group(group_name)"

resources:
  files:
    detail_csv:
      csv_file:
        path: {$init_var: out_root}
        encoding: utf-8

outputs:
  - name: detail
    to: {file: detail_csv}
    write:
      header_fields_output_by: field_id
      include_header: true
    where: "_is_valid_group"
    fields: [ticket_id, group_name, _is_valid_group]
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
                    template=DemandRunTemplateOptions(init_vars=init_vars),
                    runtime=DemandRunRuntimeOptions(batch_size=2),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            bad_exc_msg = str(exc)
            bad_fast_failed = bool(("函数签名不匹配" in bad_exc_msg) and ("too many positional arguments" in bad_exc_msg))

        good_yaml.write_text(
            """\
name: yaml_dsl_call_by_keyword_only_good

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id, name: 工单ID, value_cast: int}
    group_name: {extract: category, name: 分组名}

fields:
  _is_valid_group:
    name: 是否合法分组
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:is_valid_group(group_name=group_name)"

resources:
  files:
    detail_csv:
      csv_file:
        path: {$init_var: out_root}
        encoding: utf-8

outputs:
  - name: detail
    to: {file: detail_csv}
    write:
      header_fields_output_by: field_id
      include_header: true
    where: "_is_valid_group"
    fields: [ticket_id, group_name, _is_valid_group]
""",
            encoding="utf-8",
        )

        good_rows: List[Dict[str, str]] = []
        good_outputs = None
        good_ok = False
        try:
            compilation = compile_yaml(
                str(good_yaml),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    template=DemandRunTemplateOptions(init_vars=init_vars),
                    runtime=DemandRunRuntimeOptions(batch_size=2),
                ),
            )
            core = run_ir(compilation.demand_ir, compilation.request)
            good_outputs = sorted(core.outputs.keys()) if core.outputs else []
            detail_path = None if core.outputs is None else core.outputs.get("detail")
            out_detail = Path(str(detail_path)) if detail_path else None
            good_rows = _read_csv_rows(out_detail) if out_detail is not None and out_detail.exists() else []
            good_ok = bool(len(good_rows) == 5 and good_outputs)
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile/run failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )

        passed = bool(bad_fast_failed and good_ok)
        summary = "bad_fast_failed={} good_rows={} outputs={}".format(bad_fast_failed, len(good_rows), good_outputs)
        details: Dict[str, Any] = {
            "bad_yaml_path": str(bad_yaml),
            "bad_exc_message": bad_exc_msg,
            "good_yaml_path": str(good_yaml),
            "out_root": str(out_root),
            "detail_csv": str(out_detail) if out_detail is not None else None,
            "good_rows": len(good_rows),
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_call_by_keyword_only()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_call_by_keyword_only

        ## 背景

        YAML `call_by` 支持位置参数与 kwargs，但 **Python 函数的 keyword-only 参数**（签名里有 `*`）只能用关键字传参。

        如果把字段写成位置参数：
        - `call_by: "...:is_valid_group(group_name)"`
        - 目标函数: `def is_valid_group(*, group_name, **kw): ...`

        Python 会抛出 `TypeError`。若运行期 guardrails 把 `TypeError` 归类为可预期 compute error，
        则可能出现“字段被写成 None -> where 全过滤 -> 明细 0 行”的隐蔽故障。

        ## 本章回归点（deterministic）

        - **坏例子**：位置参数调用 keyword-only -> 必须在编译期 fast-fail（不进入执行）
        - **好例子**：显式 `group_name=group_name` -> 可正常运行并输出 5 行

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch061_yaml_dsl_call_by_keyword_only.py::run_yaml_dsl_call_by_keyword_only`
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
    result = run_yaml_dsl_call_by_keyword_only()
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
