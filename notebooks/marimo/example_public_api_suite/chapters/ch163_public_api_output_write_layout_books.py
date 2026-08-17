import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set

from scalim.dsl import yaml_dsl as api
from scalim.events import Event, EventType
from scalim.ob.observer import Observer
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXAMPLE_ID = "example_public_api_suite/ch163_public_api_output_write_layout_books"


class _PipelineTraceObserver(Observer):
    def __init__(self) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.PIPELINE_START, EventType.PIPELINE_END}
        self.seen: List[EventType] = []

    def on_event(self, event: Event) -> None:
        event_type = getattr(event, "event_type", None)
        if isinstance(event_type, EventType):
            self.seen.append(event_type)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _books_demand_yaml() -> str:
    return """\
name: public_api_layout_books

main_source:
  source_id: items
  loader: "scalim_misc.examples.public_api._fixtures:load_items"
  fields:
    item_id: {extract: item_id, name: Item ID}
    dim_id: {extract: dim_id, name: Dim ID}

sources: {}
"""


def _run_books(*, demand_path: Path, output_root: Path, runtime: api.DemandRunRuntimeOptions) -> None:
    overrides = api.RunOverrides(
        outputs=(
            api.OutputOverride(
                name="detail_book",
                fields=("item_id", "dim_id"),
                to=api.OutputToOverride(sheet="Detail"),
                write=api.OutputWriteOverride(include_header=True, header_fields_output_by="field_id"),
            ),
        ),
        resources=api.ResourcesOverride(
            books={"report": api.BookResourceOverride(path=output_root, allow_formulas=False)},
        ),
        outputs_defaults=api.OutputsDefaultsOverride(to=api.OutputDefaultsToOverride(book="report")),
    )
    _ = api.run(
        str(demand_path),
        options=api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
            runtime=runtime,
            outputs=api.DemandRunOutputOptions(overrides=overrides),
        ),
    )


def _caught_message(exc: BaseException) -> str:
    parts = ["{}: {}".format(type(exc).__name__, exc)]
    errors = getattr(exc, "errors", None)
    if errors:
        extra = "\n".join(str(getattr(item, "message", item)) for item in errors)
        if extra:
            parts.append(extra)
    return "\n".join(parts)


def run_public_api_output_write_layout_books() -> ExampleResult:
    """`YAML books / composition` 不能假装切列布局：`fail-fast`，且 `pipeline` 事件不应开始。"""
    with tempfile.TemporaryDirectory(prefix="scalim-public-api-layout-books-") as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"
        _write_text(demand_path, _books_demand_yaml())

        chunked_obs = _PipelineTraceObserver()
        buffered_obs = _PipelineTraceObserver()
        residency_obs = _PipelineTraceObserver()
        chunked_err = ""
        buffered_err = ""
        residency_err = ""
        yaml_field_err = ""

        try:
            _run_books(
                demand_path=demand_path,
                output_root=tmp / "chunked",
                runtime=api.DemandRunRuntimeOptions(
                    batch_size=10,
                    output_write_layout=api.OutputWriteLayout.COLUMN_CHUNKED,
                    components=[chunked_obs],
                ),
            )
        except Exception as exc:  # noqa: BLE001
            chunked_err = _caught_message(exc)

        try:
            _run_books(
                demand_path=demand_path,
                output_root=tmp / "buffered",
                runtime=api.DemandRunRuntimeOptions(
                    batch_size=10,
                    output_write_layout=api.OutputWriteLayout.COLUMN_BUFFERED,
                    components=[buffered_obs],
                ),
            )
        except Exception as exc:  # noqa: BLE001
            buffered_err = _caught_message(exc)

        try:
            _run_books(
                demand_path=demand_path,
                output_root=tmp / "residency",
                runtime=api.DemandRunRuntimeOptions(
                    batch_size=10,
                    excel_column_residency=api.ExcelColumnResidency.CHUNKED,
                    components=[residency_obs],
                ),
            )
        except Exception as exc:  # noqa: BLE001
            residency_err = _caught_message(exc)

        illegal_yaml = tmp / "illegal_layout.yaml"
        _write_text(illegal_yaml, _books_demand_yaml() + "\noutput_write_layout: column_chunked\n")
        try:
            _ = api.run(
                str(illegal_yaml),
                options=api.DemandRunOptions(
                    security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    runtime=api.DemandRunRuntimeOptions(batch_size=10),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            yaml_field_err = _caught_message(exc)

        chunked_ok = "output_composition" in chunked_err and EventType.PIPELINE_START not in chunked_obs.seen
        buffered_ok = "output_composition" in buffered_err and EventType.PIPELINE_START not in buffered_obs.seen
        residency_ok = "output_composition" in residency_err and EventType.PIPELINE_START not in residency_obs.seen
        yaml_ok = "output_write_layout" in yaml_field_err and "OutputWriteLayout" in yaml_field_err
        passed = bool(chunked_ok and buffered_ok and residency_ok and yaml_ok)
        details: Dict[str, Any] = {
            "chunked_err": chunked_err,
            "buffered_err": buffered_err,
            "residency_err": residency_err,
            "yaml_field_err": yaml_field_err,
            "chunked_pipeline_events": [str(item) for item in chunked_obs.seen],
            "buffered_pipeline_events": [str(item) for item in buffered_obs.seen],
            "residency_pipeline_events": [str(item) for item in residency_obs.seen],
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary="chunked_ok={} buffered_ok={} residency_ok={} yaml_ok={}".format(chunked_ok, buffered_ok, residency_ok, yaml_ok),
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_public_api_output_write_layout_books()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch163_public_api_output_write_layout_books

        本章目标:
        - YAML books / `output_composition` 不能设 `COLUMN_CHUNKED` / `COLUMN_BUFFERED`
        - `ExcelColumnResidency.CHUNKED` 同样 fail-fast（禁止假开关）
        - YAML 声明 `output_write_layout` 字段在入口即拒绝
        - fail-fast 发生在 pipeline 启动前（无 `PIPELINE_START`）

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch163_public_api_output_write_layout_books.py::run_public_api_output_write_layout_books`

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
    result = run_public_api_output_write_layout_books()
    chapter_result = {
        "passed": result.passed,
        "summary": result.summary,
        "details": result.details if result.details is not None else {},
    }
    return (chapter_result,)


@app.cell(hide_code=True)
def _(mo, chapter_result):
    mo.callout(
        mo.md("## {}".format("PASS" if chapter_result["passed"] else "FAIL")),
        kind="success" if chapter_result["passed"] else "danger",
    )
    mo.md("```\n{}\n```".format(chapter_result["summary"]))
    return


@app.cell(hide_code=True)
def _(mo, chapter_result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
