"""Cells-native marimo notebook: ch065_yaml_dsl_should_retry_signature_mismatch.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  bad YAML + should_retry 零件 + compile fast-fail 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_should_retry_signature_mismatch

        ## 回归点

        `loader_retry.default.should_retry(exc, ctx)` 签名不匹配必须编译期 `fail-fast`：
        故意传 `(*, exc, ctx)` keyword-only 形态，应报「函数签名不匹配」。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：`bad_should_retry`（keyword-only，签名不匹配触发）
        2. 内联 bad YAML + 装配 loader_retry 策略
        3. `compile` 预期 fast-fail → 检查「loader_retry.default.should_retry + 函数签名不匹配」
        4. 断言展开 → chapter_result

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
    from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        Dict,
        LoaderRetryPoliciesSpec,
        LoaderRetryPolicySpec,
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

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-should-retry-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, tmp


@app.cell
def _(Path, tmp):
    # 内联 bad YAML（行列表 join：规避 marimo 对多行字符串内缩进的变换）
    yaml_path = tmp / "bad_should_retry.yaml"
    yaml_lines = [
        "name: yaml_dsl_should_retry_signature_mismatch_bad",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id}",
    ]
    yaml_path.write_text("\n".join(yaml_lines), encoding="utf-8")
    print("yaml_path:", yaml_path)
    return yaml_lines, yaml_path


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, LoaderRetryPoliciesSpec, LoaderRetryPolicySpec, compile_yaml, yaml_path):
    # 零件: keyword-only should_retry —— 故意触发签名不匹配
    def bad_should_retry(*, exc: Exception, ctx: object) -> bool:  # type: ignore[no-untyped-def]
        _ = (exc, ctx)
        return True

    # bad：预期编译期 fast-fail（捕获预期异常做断言）
    exc_msg = ""
    bad_fast_failed = False
    try:
        _ = compile_yaml(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=DemandRunRuntimeOptions(
                    batch_size=2,
                    loader_retry=LoaderRetryPoliciesSpec(
                        default=LoaderRetryPolicySpec(enabled=True, should_retry=bad_should_retry, max_attempts=2)
                    ),
                ),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言编译期拒绝
        exc_msg = str(exc)
        bad_fast_failed = bool(
            ("loader_retry.default.should_retry" in exc_msg) and ("函数签名不匹配" in exc_msg)
        )

    print("bad_fast_failed =", bad_fast_failed)
    print("exc_message     =", exc_msg[:160])
    return bad_fast_failed, exc_msg


@app.cell
def _(bad_fast_failed, render_checks):
    checks = {"should_retry 签名不匹配编译期 fast-fail": bad_fast_failed}
    render_checks(checks)
    return checks


@app.cell
def _(bad_fast_failed, checks, exc_msg, make_chapter_result, yaml_path):
    passed = bool(all(checks.values()))
    summary = "bad_fast_failed={}".format(bad_fast_failed)
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "bad_yaml_path": str(yaml_path),
            "bad_exc_message": exc_msg,
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