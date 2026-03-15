import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_yaml

        本章目标:
        - 演示 workflow YAML 的可运行对拍入口(含 `share_preload_cache`)
        - 为 workflow 场景提供可交互排障入口

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/workflow_yaml.py::run_workflow_yaml`

        Gate:
        - `just examples`（跑全量）
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

    _ = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    workflow_yaml_path = demo_dir / "by_yaml_dsl" / "workflow_fixture.yaml"
    return Path, demo_dir, workflow_yaml_path


@app.cell(hide_code=True)
def _(mo, workflow_yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow fixture")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_path, max_lines=120)))
    return excerpt_head


@app.cell
def _(workflow_yaml_path):
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.chapters.workflow_yaml import run_workflow_yaml

    cfg = build_test_config_small()
    result = run_workflow_yaml(cfg, workflow_yaml_path=workflow_yaml_path)
    return cfg, result, run_workflow_yaml


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
