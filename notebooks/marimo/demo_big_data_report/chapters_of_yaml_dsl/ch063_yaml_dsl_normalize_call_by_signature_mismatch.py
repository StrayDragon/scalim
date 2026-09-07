"""Cells-native marimo notebook: ch063_yaml_dsl_normalize_call_by_signature_mismatch.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  bad YAML(行列表 join)、compile fast-fail 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_normalize_call_by_signature_mismatch

        ## 回归点

        `sources.*.normalize.call_by` 签名不匹配必须编译期 `fail-fast`：
        `normalize_kwonly_result(*, result)` 不接受位置参数，故意用无参调用触发。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联 bad YAML（normalize.call_by 签名不匹配）
        2. `compile` 预期 fast-fail → 检查「sources.customers.normalize.call_by + 函数签名不匹配」
        3. 断言展开 → chapter_result

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

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions
    from scalim.dsl.yaml_dsl import compile as compile_yaml
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
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

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-normalize-call-by-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, tmp


@app.cell
def _(Path, tmp):
    # 内联 bad YAML（行列表 join：规避 marimo 对多行字符串内缩进的变换）
    bad_yaml = tmp / "bad_normalize_call_by.yaml"
    bad_yaml_lines = [
        "name: yaml_dsl_normalize_call_by_signature_mismatch_bad",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id}",
        "",
        "sources:",
        "  customers:",
        '    loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_customers"',
        "    key: customer_id",
        "    params:",
        "      ids: {$keys: {as: set}}",
        "    normalize:",
        '      call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:normalize_kwonly_result"',
        "      index_by_key: {}",
    ]
    bad_yaml.write_text("\n".join(bad_yaml_lines), encoding="utf-8")
    print("bad_yaml:", bad_yaml)
    return bad_yaml, bad_yaml_lines


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, bad_yaml, compile_yaml):
    # bad：预期编译期 fast-fail（捕获预期异常做断言）
    bad_exc_msg = ""
    bad_fast_failed = False
    try:
        _ = compile_yaml(
            str(bad_yaml),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=DemandRunRuntimeOptions(batch_size=2),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言编译期拒绝
        bad_exc_msg = str(exc)
        bad_fast_failed = bool(
            ("sources.customers.normalize.call_by" in bad_exc_msg)
            and ("函数签名不匹配" in bad_exc_msg)
            and ("normalize.call_by(result" in bad_exc_msg)
        )

    print("bad_fast_failed =", bad_fast_failed)
    print("bad_exc_message =", bad_exc_msg[:160])
    return bad_exc_msg, bad_fast_failed


@app.cell
def _(bad_fast_failed, render_checks):
    checks = {"bad 编译期 fast-fail（normalize.call_by 签名）": bad_fast_failed}
    render_checks(checks)
    return checks


@app.cell
def _(bad_exc_msg, bad_fast_failed, bad_yaml, checks, make_chapter_result):
    passed = bool(all(checks.values()))
    summary = "bad_fast_failed={}".format(bad_fast_failed)
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "bad_yaml_path": str(bad_yaml),
            "bad_exc_message": bad_exc_msg,
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