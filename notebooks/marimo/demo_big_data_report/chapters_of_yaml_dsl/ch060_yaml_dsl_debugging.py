"""Cells-native marimo notebook: ch060_yaml_dsl_debugging.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  bad YAML + 预期失败断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_debugging

        ## 回归点

        一个确定性的“预期失败”章节：`where` 引用未声明字段时必须编译期报错，
        演示常见错误如何定位。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联 bad YAML（`where: "unknown_field > 0"` 故意引用未知字段）
        2. `compile` 预期失败 → 检查错误文案
        3. 断言展开 → chapter_result（passed=True = 预期失败被正确捕获）

        Gate: `just examples`
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
    _ = repo_root
    return (repo_root,)


@app.cell
def _():
    import tempfile
    from pathlib import Path
    from typing import Any, Dict

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
    from scalim.dsl.yaml_dsl import compile as compile_yaml
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        Path,
        compile_yaml,
        make_chapter_result,
        render_checks,
        tempfile,
    )


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-debug-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, tmp


@app.cell
def _(Path, tmp):
    # 内联 bad YAML（行列表 join：规避 marimo 对多行字符串内缩进的变换）
    bad_yaml = tmp / "bad_where.yaml"
    out_csv = tmp / "out.csv"
    bad_yaml_lines = [
        "name: yaml_dsl_debugging_bad_where",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {name: Ticket ID}",
        "",
        "resources:",
        "  files:",
        "    detail_csv:",
        "      csv_file:",
        "        path: {$init_var: out_path_detail}",
        "",
        "outputs:",
        "  - name: detail",
        "    to: {file: detail_csv}",
        "    write:",
        "      header_fields_output_by: field_id",
        "      include_header: true",
        '    where: "unknown_field > 0"',
        "    fields: [ticket_id]",
    ]
    bad_yaml.write_text("\n".join(bad_yaml_lines), encoding="utf-8")
    print("bad_yaml:", bad_yaml)
    return bad_yaml, bad_yaml_lines, out_csv


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, bad_yaml, compile_yaml, out_csv):
    # 预期失败：compile 必须报「where 引用未知字段」
    expected_failed = False
    exc_type = ""
    message = ""
    try:
        _ = compile_yaml(
            str(bad_yaml),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                template=DemandRunTemplateOptions(init_vars={"out_path_detail": str(out_csv)}),
                runtime=DemandRunRuntimeOptions(batch_size=2),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言编译期拒绝
        exc_type = type(exc).__name__
        message = str(exc)
        expected_failed = bool(
            ("where depends on unknown fields" in message)
            or ("Invalid where expression" in message)
            or ("unknown fields" in message)
        )

    print("expected_failed =", expected_failed)
    print("exc_type        =", exc_type)
    print("message         =", message[:160])
    return expected_failed, exc_type, message


@app.cell
def _(expected_failed, render_checks):
    checks = {"where 引用未知字段编译期报错": expected_failed}
    render_checks(checks)
    return checks


@app.cell
def _(bad_yaml, checks, exc_type, expected_failed, make_chapter_result, message):
    passed = bool(all(checks.values()))
    summary = "expected failure captured: {}: {}".format(exc_type, message[:120])
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "bad_yaml_path": str(bad_yaml),
            "hint": "Fix by changing `where` to reference declared field_id(s) only.",
            "exc_type": exc_type,
            "message": message,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()