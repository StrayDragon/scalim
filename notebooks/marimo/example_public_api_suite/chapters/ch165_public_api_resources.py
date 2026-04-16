import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet

from scalim.dsl import yaml_dsl as api
from scalim.shortcuts.resources import outputs
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXAMPLE_ID = "example_public_api_suite/ch165_public_api_resources"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _touch_public_all(module: Any) -> int:
    declared_all = getattr(module, "__all__", ())
    for name in declared_all:
        getattr(module, name)
    return len(declared_all)


def run_public_api_resources() -> ExampleResult:
    import scalim.shortcuts as shortcuts_api
    from scalim.shortcuts import resources as resources_api

    touched = {
        "scalim.shortcuts": _touch_public_all(shortcuts_api),
        "scalim.shortcuts.resources": _touch_public_all(resources_api),
        "scalim.shortcuts.resources.outputs": _touch_public_all(outputs),
    }

    with tempfile.TemporaryDirectory(prefix="scalim-public-api-resources-") as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"
        output_root = tmp / "out"

        _write_text(
            demand_path,
            """\
name: public_api_resources

main_source:
  source_id: items
  loader: "scalim_misc.examples.public_api._fixtures:load_items"
  fields:
    item_id: {extract: item_id, name: Item ID}
    dim_id: {extract: dim_id, name: Dim ID}

sources: {}
""",
        )

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
                        kind="xlsx_file",
                        path=output_root,
                        allow_formulas=False,
                        write_defaults=api.BookWriteDefaultsOverride(mode="sheet"),
                    )
                },
                files={"detail_csv": api.FileResourceOverride(kind="csv_file", path=output_root, encoding="utf-8")},
            ),
            outputs_defaults=api.OutputsDefaultsOverride(to=api.OutputDefaultsToOverride(book="report")),
        )

        run_result = api.run(
            str(demand_path),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                runtime=api.DemandRunRuntimeOptions(batch_size=10),
                outputs=api.DemandRunOutputOptions(overrides=overrides, capture=api.CaptureRows()),
            ),
        )
        captured_rows = run_result.captured_rows
        rows = [] if captured_rows is None else list(captured_rows.iter_row_data())

        latest = outputs.load_latest_outputs(output_root)
        report_xlsx = outputs.latest_book_path(output_root, book_id="report")
        detail_csv = outputs.latest_file_path(output_root, file_id="detail_csv")

        passed = bool(latest.run_id and report_xlsx.exists() and detail_csv.exists())
        summary = "run_id={} books={} files={}".format(
            latest.run_id,
            sorted(latest.books.keys()),
            sorted(latest.files.keys()),
        )
        details: Dict[str, Any] = {
            "run_id": latest.run_id,
            "report_xlsx": str(report_xlsx),
            "detail_csv": str(detail_csv),
            "touched_public_all": touched,
            "rows": len(rows),
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_public_api_resources()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch165_public_api_resources

        本章目标:
        - 演示稳定 facade: `scalim.shortcuts.resources.outputs`
        - 从 output root 定位最新一次发布的 workbook/books 与 files

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch165_public_api_resources.py::run_public_api_resources`

        Gate:
        - `just examples`
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
    return


@app.cell
def _():
    result = run_public_api_resources()
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
