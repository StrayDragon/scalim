"""Cells-native marimo notebook: ch064_yaml_dsl_loader_params_signature_mismatch.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  bad YAML×2(行列表 join)、compile fast-fail 断言全部在 cells 内

注意: `load_required_flag` 是本模块级零件 —— bad_missing YAML 以
`notebooks...ch064_...:load_required_flag` 引用它,cell 定义不会写入模块
globals,故该 loader 零件必须留在模块级(app.run() 之外)。
"""

import marimo

from typing import Any, Dict, Mapping

__generated_with = "0.22.0"
app = marimo.App(width="full")


def load_required_flag(flag: int, tag: str = "x") -> Mapping[int, Dict[str, object]]:
    """模块级 loader 零件：仅作为签名校验目标（flag 必填、tag 可选）。"""
    _ = (flag, tag)
    return {}


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_loader_params_signature_mismatch

        ## 回归点

        `sources.*.params` 顶层 `kwargs` 键与 loader 签名不匹配必须编译期 `fail-fast`：
        - unknown：`bad_key: 1`（loader 无此参数）
        - missing：`s1` 引用 `load_required_flag`（缺必填 `flag`）

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联两份 bad YAML（unknown / missing，行列表 join）
        2. `compile` 各自预期 fast-fail → 检查错误文案
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

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-loader-params-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    ALLOWED_MODULES = frozenset(
        [
            "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario",
            "notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.ch064_yaml_dsl_loader_params_signature_mismatch",
        ]
    )
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, tmp


@app.cell
def _(Path, tmp):
    # 内联 bad YAML ×2（行列表 join：规避 marimo 对多行字符串内缩进的变换）
    bad_unknown_yaml = tmp / "bad_params_unknown.yaml"
    bad_unknown_lines = [
        "name: yaml_dsl_loader_params_signature_mismatch_unknown",
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
        "      bad_key: 1",
    ]
    bad_unknown_yaml.write_text("\n".join(bad_unknown_lines), encoding="utf-8")

    bad_missing_yaml = tmp / "bad_params_missing.yaml"
    bad_missing_lines = [
        "name: yaml_dsl_loader_params_signature_mismatch_missing",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id}",
        "",
        "sources:",
        "  s1:",
        '    loader: "notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.ch064_yaml_dsl_loader_params_signature_mismatch:load_required_flag"',
        "    key: id",
        "    params:",
        '      tag: "demo"',
    ]
    bad_missing_yaml.write_text("\n".join(bad_missing_lines), encoding="utf-8")
    print("bad_unknown_yaml:", bad_unknown_yaml)
    print("bad_missing_yaml:", bad_missing_yaml)
    return bad_missing_yaml, bad_missing_lines, bad_unknown_yaml, bad_unknown_lines


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, bad_unknown_yaml, compile_yaml):
    # bad-1：unknown params key 预期编译期 fast-fail
    unknown_msg = ""
    unknown_failed = False
    try:
        _ = compile_yaml(
            str(bad_unknown_yaml),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=DemandRunRuntimeOptions(batch_size=2),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言编译期拒绝
        unknown_msg = str(exc)
        unknown_failed = bool(("sources.customers.params" in unknown_msg) and ("bad_key" in unknown_msg))

    print("unknown_failed =", unknown_failed)
    return unknown_failed, unknown_msg


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, bad_missing_yaml, compile_yaml):
    # bad-2：missing required param 预期编译期 fast-fail
    missing_msg = ""
    missing_failed = False
    try:
        _ = compile_yaml(
            str(bad_missing_yaml),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=DemandRunRuntimeOptions(batch_size=2),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言编译期拒绝
        missing_msg = str(exc)
        missing_failed = bool(("sources.s1.params" in missing_msg) and ("missing" in missing_msg or "required" in missing_msg))

    print("missing_failed =", missing_failed)
    return missing_failed, missing_msg


@app.cell
def _(missing_failed, render_checks, unknown_failed):
    checks = {
        "unknown params 编译期 fast-fail": unknown_failed,
        "missing required param 编译期 fast-fail": missing_failed,
    }
    render_checks(checks)
    return checks


@app.cell
def _(bad_missing_yaml, bad_unknown_yaml, checks, make_chapter_result, missing_failed, missing_msg, unknown_failed, unknown_msg):
    passed = bool(all(checks.values()))
    summary = "unknown_failed={} missing_failed={}".format(unknown_failed, missing_failed)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"unknown_params_fast_fail": True, "missing_required_param_fast_fail": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "bad_unknown_yaml_path": str(bad_unknown_yaml),
            "bad_unknown_exc_message": unknown_msg,
            "bad_missing_yaml_path": str(bad_missing_yaml),
            "bad_missing_exc_message": missing_msg,
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
