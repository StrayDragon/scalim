import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl

        本章目标:
        - 演示 canonical YAML 的加载/编译/执行闭环(含对拍)
        - 作为 YAML DSL 语义回归的可交互入口

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/yaml_dsl.py::run_yaml_dsl`

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
    yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"
    return Path, demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_by_regex

    snippet = excerpt_by_regex(
        yaml_path,
        start_regex=r"^imports:",
        end_regex=r"^# ==============================================================================",
        max_lines=80,
    )
    mo.md("## Canonical YAML 片段：`imports`")
    mo.md("```yaml\n{}\n```".format(snippet))
    return excerpt_by_regex, snippet


@app.cell
def _(yaml_path):
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.chapters.yaml_dsl import run_yaml_dsl

    cfg = build_test_config_small()
    result = run_yaml_dsl(cfg, yaml_path=yaml_path)
    return cfg, result, run_yaml_dsl


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
