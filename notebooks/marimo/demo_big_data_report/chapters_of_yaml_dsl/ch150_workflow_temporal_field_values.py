"""Cells-native marimo notebook: ch150_workflow_temporal_field_values.

迁移对照:
  Before: 模块级 run_*() + _run_in_dir 闭包持全部逻辑;cells 薄壳
  After:  工作副本/运行/产物定位/oracle 全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_temporal_field_values

        ## 回归点

        workflow 中的时间语义字段值（temporal field values）：经 workflow 运行 +
        `report.xlsx` 产物，用 `verify_temporal_field_values_example` 对拍。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 配置 + 工作副本（workflow + demand 拷贝到临时目录）
        2. `run_workflow`（cwd=out_dir + path_aliases）
        3. 产物定位（report.xlsx 最新版本）
        4. oracle 对拍（verify_temporal_field_values_example）
        5. 汇总 chapter_result

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
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_temporal_field_values.yaml"
    _ = repo_root
    return Path, demo_dir, repo_root, workflow_yaml_path


@app.cell
def _(Path):
    import os
    import shutil
    import tempfile
    from typing import Any, Dict, Optional

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
    from scalim.shortcuts.resources import outputs as outputs_api
    from scalim_misc.demo_big_data_report.temporal_field_values_demo import verify_temporal_field_values_example
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunSecurityOptions,
        Dict,
        Optional,
        Path,
        WorkflowRunOptions,
        make_chapter_result,
        os,
        outputs_api,
        render_checks,
        run_workflow,
        shutil,
        tempfile,
        verify_temporal_field_values_example,
    )


@app.cell
def _(Path, repo_root, shutil, tempfile):
    import atexit

    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.temporal_field_values_demo"])

    out_dir = Path(tempfile.mkdtemp(prefix="scalim_temporal_fv_")).resolve()
    atexit.register(lambda: shutil.rmtree(out_dir, ignore_errors=True))
    out_root = out_dir / "out"
    shutil.rmtree(str(out_root), ignore_errors=True)
    try:
        (out_dir / "workflow.yaml").unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    print("out_dir:", out_dir)
    return allowed_modules, out_dir, out_root


@app.cell
def _(out_dir, workflow_yaml_path):
    # 工作副本: workflow.yaml + demand 拷贝
    demand_name = "workflow_demo_temporal_field_values_demand.yaml"
    wf_copy = out_dir / "workflow.yaml"
    wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out_dir / demand_name).write_text(
        (workflow_yaml_path.parent / demand_name).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    print("wf_copy:", wf_copy)
    return demand_name, wf_copy


@app.cell
def _(DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, allowed_modules, os, repo_root, run_workflow, wf_copy):
    prev_cwd = os.getcwd()
    os.chdir(str(wf_copy.parent))
    try:
        result = run_workflow(
            str(wf_copy),
            options=WorkflowRunOptions(
                demand=DemandRunOptions(
                    security=DemandRunSecurityOptions(
                        allowed_modules=allowed_modules,
                        allowed_yaml_roots=(str(repo_root),),
                    )
                ),
                path_aliases={"@": str(repo_root)},
            ),
        )
    finally:
        os.chdir(prev_cwd)

    errors = result.errors()
    print("outcomes =", [o.run_id for o in result.outcomes])
    print("errors   =", len(errors))
    return errors, result


@app.cell
def _(out_root, outputs_api):
    latest = outputs_api.load_latest_outputs(out_root)
    report_xlsx = latest.books.get("report")
    print("report_xlsx =", report_xlsx)
    return latest, report_xlsx


@app.cell
def _(errors, render_checks, report_xlsx, verify_temporal_field_values_example):
    # oracle 对拍
    oracle_result = verify_temporal_field_values_example(
        example_id="demo_big_data_report/workflow_temporal_field_values",
        book_path=report_xlsx,
        errors=errors,
    )
    checks = {"temporal field values 对拍通过": bool(oracle_result.passed)}
    render_checks(checks)
    return oracle_result, checks


@app.cell
def _(checks, make_chapter_result, oracle_result):
    passed = bool(all(checks.values()))
    summary = str(oracle_result.summary)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"oracle_passed": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "oracle": oracle_result.details,
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
