"""Cells-native marimo notebook: ch020_min_yaml.

迁移对照:
  Before: cells 薄壳调用 support/min_yaml.py::run_min_yaml()（运行装配在零件里）
  After:  YAML 定位/RunOverrides/run/期望/断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch020_min_yaml

        最小可跑 YAML DSL（假数据闭环）。

        教程核心全部在下方 cells 内逐步展开（无需跳转 support 实现）：

        1. 定位 `min_yaml_example.yaml`（canonical YAML SSOT）并展示内容
        2. `RunOverrides`（输出落到临时目录）+ `run`
        3. 期望 vs 实际对拍（3 行；methods = {card, cash}；`total_amount = amount * 2`）

        零件: `support/min_yaml_loaders.py`（YAML loader_ref 引用的模块路径，保持稳定）
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
    # ① 定位 canonical YAML 与其 loader 模块（loader 路径写死在 YAML 内，保持稳定）
    from pathlib import Path

    suite_dir = Path(__file__).resolve().parents[1]
    yaml_path = suite_dir / "support" / "min_yaml_example.yaml"
    loader_module = "notebooks.marimo.example_readme_suite.support.min_yaml_loaders"
    return loader_module, suite_dir, yaml_path


@app.cell
def _():
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return make_chapter_result, render_checks


@app.cell
def _(mo, yaml_path):
    mo.md("**min_yaml_example.yaml**:\n\n```yaml\n{}\n```".format(yaml_path.read_text(encoding="utf-8")))
    return (yaml_path,)


@app.cell
def _():
    from scalim.dsl.yaml_dsl import (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        FileResourceOverride,
        ResourcesOverride,
        RunOverrides,
        run,
    )

    return (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        FileResourceOverride,
        ResourcesOverride,
        RunOverrides,
        run,
    )


@app.cell
def _(
    CaptureRows,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    FileResourceOverride,
    ResourcesOverride,
    RunOverrides,
    loader_module,
    run,
    yaml_path,
):
    # ② 运行：输出重定向到临时目录，捕获行做对拍
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory(prefix="scalim-readme-yaml-") as tmp:
        out_root = _Path(tmp) / "output"
        out_root.mkdir(parents=True, exist_ok=True)
        overrides = RunOverrides(
            resources=ResourcesOverride(
                files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(out_root))},
            )
        )
        result = run(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=frozenset([loader_module])),
                outputs=DemandRunOutputOptions(capture=CaptureRows(), overrides=overrides),
            ),
        )
    captured_rows = list(result.captured_rows.iter_row_data()) if result.captured_rows is not None else []
    total_rows = int(result.total_rows)
    print("total_rows =", total_rows)
    return captured_rows, total_rows


@app.cell
def _(captured_rows, mo, total_rows):
    # ③ 期望 vs 实际（期望值是教学 payload，直接写在 cells 里）
    expected_rows = [
        {"order_id": 1, "method": "card", "total_amount": 20.0},
        {"order_id": 2, "method": "cash", "total_amount": 41.0},
        {"order_id": 3, "method": "card", "total_amount": 14.0},
    ]
    keys = ("order_id", "method", "total_amount")
    actual_rows = sorted(
        ({k: row.get(k) for k in keys} for row in captured_rows),
        key=lambda row: row["order_id"],
    )
    methods = {str(row.get("method")) for row in captured_rows}
    mo.vstack(
        [
            mo.md("**期望 vs 实际**（关联 `method` + 计算 `total_amount = amount * 2`）："),
            mo.ui.table(
                [{"kind": "期望", **row} for row in expected_rows] + [{"kind": "实际", **row} for row in actual_rows],
                selection=None,
            ),
        ]
    )
    return actual_rows, expected_rows, methods


@app.cell
def _(actual_rows, expected_rows, make_chapter_result, methods, render_checks, total_rows):
    # ④ 对拍断言 + 结构化 chapter_result
    checks = {
        "YAML 运行 3 行": total_rows == 3,
        "methods = {card, cash}": methods == {"card", "cash"},
        "期望行完全一致": actual_rows == expected_rows,
    }
    render_checks(checks)
    passed = bool(all(checks.values()))
    summary = "rows={} methods={}".format(total_rows, sorted(methods))
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "rows": total_rows,
            "methods": sorted(methods),
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, checks, passed, summary


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
