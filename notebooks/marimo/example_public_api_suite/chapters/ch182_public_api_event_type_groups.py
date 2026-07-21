import marimo

from typing import Any, Dict, List

from scalim.events import EventType, type_groups
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch182_public_api_event_type_groups"


def _collect_event_types(node: Any) -> List[EventType]:
    if isinstance(node, EventType):
        return [node]
    if hasattr(node, "__dict__"):
        out: List[EventType] = []
        for value in getattr(node, "__dict__", {}).values():
            out.extend(_collect_event_types(value))
        return out
    return []


def run_public_api_event_type_groups() -> ExampleResult:
    values: List[EventType] = []
    for group_name in type_groups.__all__:
        values.extend(_collect_event_types(getattr(type_groups, group_name)))

    expected_pairs = [
        ("pipeline.start", type_groups.pipeline.start, EventType.PIPELINE_START),
        ("pipeline.end", type_groups.pipeline.end, EventType.PIPELINE_END),
        ("loader.call", type_groups.loader.call, EventType.LOADER_CALL),
        ("field.compute", type_groups.field.compute, EventType.FIELD_COMPUTE),
        ("workflow.node.start", type_groups.workflow.node.start, EventType.WORKFLOW_NODE_START),
        ("workflow.node.end", type_groups.workflow.node.end, EventType.WORKFLOW_NODE_END),
    ]

    valid_enum_values = all(isinstance(v, EventType) for v in values)
    no_new_values = set(values).issubset(set(EventType))
    pairs_ok = all(left == right for _, left, right in expected_pairs)

    passed = bool(values and valid_enum_values and no_new_values and pairs_ok)
    summary = "values={} unique={} pairs_ok={}".format(len(values), len(set(values)), pairs_ok)
    details: Dict[str, Any] = {
        "pairs": [{"id": k, "value": str(left), "expected": str(right), "ok": left == right} for k, left, right in expected_pairs],
        "unique_values": sorted({str(v) for v in values}),
    }
    return ExampleResult(
        example_id=_EXAMPLE_ID,
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_event_type_groups()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch182_public_api_event_type_groups

        本章目标:
        - 演示稳定入口: `scalim.events.type_groups` 的“事件类型分组视图”
        - 确保它仅提升可发现性(不引入新事件类型值)

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch182_public_api_event_type_groups.py::run_public_api_event_type_groups`

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
    result = run_public_api_event_type_groups()
    chapter_result = {
        "passed": chapter_result["passed"],
        "summary": chapter_result["summary"],
        "details": chapter_result["details"] if chapter_result["details"] is not None else {},
    }
    return (chapter_result,)


@app.cell(hide_code=True)
def _(mo, chapter_result):
    mo.callout(
        mo.md("## {}".format("PASS" if chapter_result["passed"] else "FAIL")), kind="success" if chapter_result["passed"] else "danger"
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
