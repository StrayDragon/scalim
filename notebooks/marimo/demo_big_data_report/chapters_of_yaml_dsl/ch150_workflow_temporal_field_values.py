import marimo

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.shortcuts.resources import outputs as outputs_api
from scalim_misc.demo_big_data_report.temporal_field_values_demo import verify_temporal_field_values_example
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "demo_big_data_report/workflow_temporal_field_values"


def run_workflow_temporal_field_values(
    *,
    workflow_yaml_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    clean_output_dir: bool = True,
) -> ExampleResult:
    if workflow_yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_temporal_field_values.yaml"

    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.temporal_field_values_demo"])
    repo_root = Path(__file__).resolve().parents[4]

    def _run_in_dir(out_dir: Path) -> ExampleResult:
        out_root = out_dir / "out"
        if clean_output_dir:
            shutil.rmtree(str(out_root), ignore_errors=True)
            try:
                (out_dir / "workflow.yaml").unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

        demand_name = "workflow_demo_temporal_field_values_demand.yaml"
        wf_copy = out_dir / "workflow.yaml"
        wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")
        (out_dir / demand_name).write_text((workflow_yaml_path.parent / demand_name).read_text(encoding="utf-8"), encoding="utf-8")

        try:
            prev_cwd = os.getcwd()
            os.chdir(str(out_dir))
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
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="workflow failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__},
            )

        errors = result.errors()
        report_xlsx = None
        try:
            latest = outputs_api.load_latest_outputs(out_root)
            report_xlsx = latest.books.get("report")
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="load_latest_outputs failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "errors": errors},
            )

        return verify_temporal_field_values_example(
            example_id=_EXAMPLE_ID,
            book_path=report_xlsx,
            errors=errors,
        )

    if output_dir is None:
        with tempfile.TemporaryDirectory(prefix="scalim_temporal_fv_") as tmp:
            return _run_in_dir(Path(tmp))
    return _run_in_dir(Path(output_dir))


def run_chapter() -> ExampleResult:
    return run_workflow_temporal_field_values()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_temporal_field_values

        ## 背景

        `c5` 之后 workflow xlsx 中间态为 typed `InMemoryRows`。若 `FieldValue` 不含时间类型，
        loader 返回的 `datetime`/`date`/`time`/`timedelta` 曾被 `str()`，Excel 变成文本列。

        ## 对拍点

        - 最小 1-run workflow → 共享 `xlsx` book
        - 读回单元格：`data_type == "d"`，Python 类型为时间类型（不是 `str`）
        - `order_id` 仍为数值（回归）

        Gate: `just examples` / `just qa`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch150_workflow_temporal_field_values.py::run_workflow_temporal_field_values`
        - `packages/scalim-misc/.../temporal_field_values_demo.py`
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
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_temporal_field_values.yaml"
    return demo_dir, workflow_yaml_path


@app.cell(hide_code=True)
def _(mo, workflow_yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow fixture")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_path, max_lines=80)))
    return excerpt_head


@app.cell
def _(workflow_yaml_path):
    result = run_workflow_temporal_field_values(workflow_yaml_path=workflow_yaml_path)
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
