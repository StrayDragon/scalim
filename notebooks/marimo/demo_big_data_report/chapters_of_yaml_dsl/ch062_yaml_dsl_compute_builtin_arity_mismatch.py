"""Cells-native marimo notebook: ch062_yaml_dsl_compute_builtin_arity_mismatch.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  bad YAML(行列表 join,规避 marimo 多行字符串缩进 mod-4 变换)、
          compile fast-fail 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_compute_builtin_arity_mismatch

        ## 回归点

        `compute` 表达式中 `SAFE_FUNCTIONS` 内置函数调用形态必须编译期 `fail-fast`：
        `len(a, b)` 等 arity mismatch 不进入运行期 `guardrails` 吞错语义。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联 bad YAML（`compute: "len(ticket_id, group_name)"` 故意 2 参数）
        2. `compile` 预期 fast-fail → 检查「调用形态不匹配 + len」
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
    from typing import Any, Dict, List

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions
    from scalim.dsl.yaml_dsl import compile as compile_yaml
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        Dict,
        List,
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

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-compute-arity-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, tmp


@app.cell
def _(Path, tmp):
    # 内联 bad YAML（行列表 join：规避 marimo 对多行字符串内缩进的变换）
    bad_yaml = tmp / "bad_compute.yaml"
    bad_yaml_lines = [
        "name: yaml_dsl_compute_builtin_arity_mismatch_bad",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id}",
        "    group_name: {extract: category}",
        "",
        "fields:",
        "  _bad:",
        "    depends_on: [ticket_id, group_name]",
        '    compute: "len(ticket_id, group_name)"',
    ]
    bad_yaml.write_text("\n".join(bad_yaml_lines), encoding="utf-8")
    print("bad_yaml:", bad_yaml)
    return bad_yaml, bad_yaml_lines


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, List, bad_yaml, compile_yaml):
    # bad：预期编译期 fast-fail（捕获预期异常做断言）
    bad_errors: List[str] = []
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

    print("bad_fast_failed =", bad_fast_failed)
    print("errors          =", bad_errors[:3])
    return bad_errors, bad_fast_failed


@app.cell
def _(bad_errors, bad_fast_failed, bad_yaml, checks, make_chapter_result):
    passed = bool(all(checks.values()))
    summary = "bad_fast_failed={} errors={}".format(bad_fast_failed, len(bad_errors))
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"bad_compile_fast_fail": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "bad_yaml_path": str(bad_yaml),
            "bad_errors": bad_errors[:10],
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell
def _(bad_fast_failed, render_checks):
    checks = {"bad 编译期 fast-fail（len 双参）": bad_fast_failed}
    render_checks(checks)
    return checks


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
