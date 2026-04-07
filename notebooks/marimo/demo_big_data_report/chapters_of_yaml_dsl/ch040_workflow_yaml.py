import marimo

from pathlib import Path
from typing import Any, Dict, Optional

from scalim.dsl.by_yaml import RunOptions, run_workflow
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import (
    ECommerceConfig,
    get_config,
    get_workflow_preload_counter_calls,
    reset_workflow_preload_counter_calls,
    set_config,
)
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")
_EXAMPLE_ID = "demo_big_data_report/workflow_yaml"


def run_workflow_yaml(
    cfg: Optional[ECommerceConfig] = None,
    *,
    workflow_yaml_path: Optional[Path] = None,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    if workflow_yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture.yaml"
    prev = get_config()
    set_config(cfg)
    try:
        allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders"])
        reset_workflow_preload_counter_calls()

        try:
            result = run_workflow(
                str(workflow_yaml_path),
                options=RunOptions(
                    allowed_modules=allowed_modules,
                    init_vars={"order_ids": []},
                ),
            )
        except Exception as exc:  # noqa: BLE001
            summary = "workflow failed: {}: {}".format(type(exc).__name__, exc)
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details={"exc_type": type(exc).__name__},
            )

        errors = result.errors()
        preload_calls = get_workflow_preload_counter_calls()
        run_ids = [o.run_id for o in result.outcomes]

        passed = bool(not errors and preload_calls == 1 and run_ids == ["r1", "r2"])
        summary = "outcomes={} preload_calls={} errors={}".format(len(result.outcomes), preload_calls, len(errors))
        if errors:
            summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)

        details: Dict[str, Any] = {
            "run_ids": run_ids,
            "preload_calls": preload_calls,
            "errors": errors,
            "outcomes": result.outcomes,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_workflow_yaml()


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

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/workflow_fixture.yaml`
        - 断言：共享 cache_pool 下 `preload_forever` loader 仅调用 1 次
        - Gate：`just examples`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch040_workflow_yaml.py::run_workflow_yaml`
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
    demo_dir = Path(__file__).resolve().parents[1]
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture.yaml"
    return demo_dir, workflow_yaml_path


@app.cell(hide_code=True)
def _(mo, workflow_yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow fixture")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_path, max_lines=120)))
    return excerpt_head


@app.cell
def _(workflow_yaml_path):
    cfg = build_test_config_small()
    result = run_workflow_yaml(cfg, workflow_yaml_path=workflow_yaml_path)
    return cfg, result


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
