"""Cells-native marimo notebook: ch040_workflow_yaml.

迁移对照:
  Before: 模块级 run_workflow_yaml() 持全部逻辑;cells 薄壳
  After:  装配/运行/断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_yaml

        ## 背景

        假设我们已经有若干份 demand YAML（单份需求配置）。工程上经常需要把它们“编排起来”：
        - 串行/并行跑多份 demand
        - 控制最大并发
        - 共享/复用 cache（例如 `preload_forever` 小表）

        ## 需求方提问（自然语言）

        平台同学：能不能给一个最小的 workflow YAML，让我在 CI 里稳定回归 workflow 语义？

        ## 方案选择（取舍）

        - 手写 Python 编排：灵活，但复用/规范/校验差
        - **workflow YAML（本章）**：把编排结构做成可 schema 校验的 YAML，且纳入 `just examples`

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 配置（`build_test_config_small`）+ set_config
        2. 装配 workflow runtime（cache_pool preload + 并发）+ `run_workflow`
        3. 断言：无 errors + preload 仅 1 次 + run_ids 顺序
        4. 汇总 chapter_result

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/workflow_fixture.yaml`
        - 断言：运行入口启用 workflow-scope cache_pool preset 后 `preload_forever` loader 仅调用 1 次
        - Gate：`just examples`
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
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture.yaml"
    _ = repo_root
    return Path, demo_dir, workflow_yaml_path


@app.cell(hide_code=True)
def _(mo, workflow_yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow fixture")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_path, max_lines=120)))
    return (excerpt_head,)


@app.cell
def _():
    from typing import Any, Dict, Optional

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, WorkflowRunOptions, run_workflow
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowCachePoolPreloadForeverShared, WorkflowExecutionOptions, WorkflowRuntimeOptions
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.loaders import (
        ECommerceConfig,
        get_workflow_preload_counter_calls,
        reset_workflow_preload_counter_calls,
        set_config,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        ECommerceConfig,
        Optional,
        WorkflowCachePoolPreloadForeverShared,
        WorkflowExecutionOptions,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        build_test_config_small,
        get_workflow_preload_counter_calls,
        make_chapter_result,
        render_checks,
        reset_workflow_preload_counter_calls,
        run_workflow,
        set_config,
    )


@app.cell
def _(build_test_config_small, reset_workflow_preload_counter_calls, set_config):
    cfg = build_test_config_small()
    set_config(cfg)
    reset_workflow_preload_counter_calls()
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders"])
    print("customer_count =", cfg.customer_count)
    return allowed_modules, cfg


@app.cell
def _(DemandRunOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, WorkflowCachePoolPreloadForeverShared, WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions, allowed_modules, get_workflow_preload_counter_calls, run_workflow, workflow_yaml_path):
    workflow_runtime_options = WorkflowRuntimeOptions(
        execution=WorkflowExecutionOptions(max_concurrency=2, failure_policy="all_fail"),
        cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16),
    )
    demand_options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
        template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
    )

    result = run_workflow(
        str(workflow_yaml_path),
        options=WorkflowRunOptions(demand=demand_options, runtime=workflow_runtime_options),
    )

    errors = result.errors()
    preload_calls = get_workflow_preload_counter_calls()
    run_ids = [o.run_id for o in result.outcomes]

    print("outcomes      =", [o.run_id for o in result.outcomes])
    print("preload_calls =", preload_calls)
    print("errors        =", len(errors))

    return demand_options, errors, preload_calls, result, run_ids, workflow_runtime_options


@app.cell
def _(errors, preload_calls, render_checks, run_ids):
    checks = {
        "无 errors": not errors,
        "preload 仅 1 次": preload_calls == 1,
        "run_ids == [r1, r2]": run_ids == ["r1", "r2"],
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, errors, make_chapter_result, preload_calls, result, run_ids):
    passed = bool(all(checks.values()))
    summary = "outcomes={} preload_calls={} errors={}".format(len(result.outcomes), preload_calls, len(errors))
    if errors:
        summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "run_ids": run_ids,
            "preload_calls": preload_calls,
            "errors": errors,
            "outcomes": result.outcomes,
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