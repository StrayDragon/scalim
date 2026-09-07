"""Cells-native marimo notebook: ch165_public_api_resources.

迁移对照:
  Before: 模块级 run_public_api_resources() 持全部逻辑;cells 薄壳
  After:  shortcuts.resources 触达 + book/file 产物定位在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch165_public_api_resources

        本章目标:
        - 演示稳定 facade: `scalim.shortcuts.resources.outputs`
        - 从 output root 定位最新一次发布的 workbook/books 与 files

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 触达 shortcuts/resources/outputs 的 public `__all__`
        2. 内联 demand YAML + ResourcesOverride（book+file）
        3. `run` → 产物落 output_root
        4. 断言：latest run_id + report.xlsx + detail.csv 存在
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
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, FrozenSet

    from scalim.dsl import yaml_dsl as api
    from scalim.shortcuts.resources import outputs
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, FrozenSet, Path, api, make_chapter_result, outputs, render_checks, tempfile


@app.cell
def _(Any, Dict, Path):
    # 零件: 文本写入 / public __all__ 触达
    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    def touch_public_all(module: Any) -> int:
        declared_all = getattr(module, "__all__", ())
        for name in declared_all:
            getattr(module, name)
        return len(declared_all)

    return touch_public_all, write_text


@app.cell
def _(FrozenSet, Path, api, outputs, tempfile, touch_public_all, write_text):
    import atexit
    import shutil

    ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])

    import scalim.shortcuts as shortcuts_api
    from scalim.shortcuts import resources as resources_api

    touched = {
        "scalim.shortcuts": touch_public_all(shortcuts_api),
        "scalim.shortcuts.resources": touch_public_all(resources_api),
        "scalim.shortcuts.resources.outputs": touch_public_all(outputs),
    }

    tmp = Path(tempfile.mkdtemp(prefix="scalim-public-api-resources-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    demand_path = tmp / "demand.yaml"
    output_root = tmp / "out"

    demand_yaml = "\n".join(
        [
            "name: public_api_resources",
            "",
            "main_source:",
            "  source_id: items",
            '  loader: "scalim_misc.examples.public_api._fixtures:load_items"',
            "  fields:",
            "    item_id: {extract: item_id, name: Item ID}",
            "    dim_id: {extract: dim_id, name: Dim ID}",
            "",
            "sources: {}",
        ]
    )
    write_text(demand_path, demand_yaml)
    print("touched:", touched)
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, demand_path, output_root, resources_api, shortcuts_api, tmp, touched


@app.cell
def _(ALLOWED_MODULES, api, demand_path, output_root):
    # 装配: book + file 资源 override + run
    overrides = api.RunOverrides(
        outputs=(
            api.OutputOverride(
                name="detail_book",
                fields=("item_id", "dim_id"),
                to=api.OutputToOverride(sheet="Detail"),
                write=api.OutputWriteOverride(include_header=True, header_fields_output_by="field_id"),
            ),
            api.OutputOverride(
                name="detail_file",
                fields=("item_id", "dim_id"),
                to=api.OutputToOverride(file="detail_csv"),
                write=api.OutputWriteOverride(include_header=True, header_fields_output_by="field_id"),
            ),
        ),
        resources=api.ResourcesOverride(
            books={
                "report": api.BookResourceOverride(
                    path=output_root,
                    allow_formulas=False,
                )
            },
            files={"detail_csv": api.FileResourceOverride(kind="csv_file", path=output_root, encoding="utf-8")},
        ),
        outputs_defaults=api.OutputsDefaultsOverride(to=api.OutputDefaultsToOverride(book="report")),
    )

    run_result = api.run(
        str(demand_path),
        options=api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(batch_size=10),
            outputs=api.DemandRunOutputOptions(overrides=overrides, capture=api.CaptureRows()),
        ),
    )
    captured_rows = run_result.captured_rows
    rows = [] if captured_rows is None else list(captured_rows.iter_row_data())
    print("rows =", len(rows))
    return overrides, rows, run_result


@app.cell
def _(outputs, output_root):
    # 产物定位
    latest = outputs.load_latest_outputs(output_root)
    report_xlsx = outputs.latest_book_path(output_root, book_id="report")
    detail_csv = outputs.latest_file_path(output_root, file_id="detail_csv")
    print("run_id:", latest.run_id)
    print("books:", sorted(latest.books.keys()), "files:", sorted(latest.files.keys()))
    return detail_csv, latest, report_xlsx


@app.cell
def _(detail_csv, render_checks, report_xlsx, latest):
    checks = {
        "latest run_id 存在": bool(latest.run_id),
        "report.xlsx 产物存在": report_xlsx.exists(),
        "detail.csv 产物存在": detail_csv.exists(),
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, detail_csv, latest, make_chapter_result, report_xlsx, rows, touched):
    passed = bool(all(checks.values()))
    summary = "run_id={} books={} files={}".format(
        latest.run_id,
        sorted(latest.books.keys()),
        sorted(latest.files.keys()),
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "run_id": latest.run_id,
            "report_xlsx": str(report_xlsx),
            "detail_csv": str(detail_csv),
            "touched_public_all": touched,
            "rows": len(rows),
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
