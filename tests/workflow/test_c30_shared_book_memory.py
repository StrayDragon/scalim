"""c30 shared-book memory release + xlsx_memory budget regression."""

from pathlib import Path

import pytest


def test_resource_manager_commit_clears_workbook_and_sheetbook_plan_segments(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from scalim.execution import versioned_outputs
    from scalim.sinks.rows import InMemoryRows
    from scalim.workflow import resources as resources_mod

    class _Instrumentation:
        def __init__(self) -> None:
            self.events = []

        def emit(self, event_type, payload, meta=None):  # type: ignore[no-untyped-def]
            self.events.append({"event_type": str(event_type), "payload": payload, "meta": meta})

    layout = versioned_outputs.ensure_output_root_layout(tmp_path / "out")
    workbook_path = versioned_outputs.book_output_path(layout, version_id="wf", book_id="report")
    export_path = versioned_outputs.book_output_path(layout, version_id="wf", book_id="mem")
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
        sheetbook_defs={
            "mem": resources_mod.SheetBookDef(
                resource_id="mem",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=str(export_path),
            )
        },
    )
    rows = InMemoryRows(header=["id"], rows=[["a1"]])
    manager.apply_workbook_sheet(
        workflow_node_id="n0",
        decl_order=0,
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv=rows,
        on_conflict="error",
    )
    manager.apply_sheetbook_sheet(
        workflow_node_id="n1",
        decl_order=1,
        sheetbook_id="mem",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv=rows,
        on_conflict="error",
    )

    assert "report" in manager._workbooks  # noqa: SLF001
    assert "mem" in manager._sheetbooks  # noqa: SLF001

    with caplog.at_level(logging.INFO, logger="scalim.workflow.resources"):
        manager.commit_all()

    assert workbook_path.exists()
    assert export_path.exists()
    assert "report" not in manager._workbooks  # noqa: SLF001
    assert "mem" not in manager._sheetbooks  # noqa: SLF001
    assert "release_reason=commit" in caplog.text


def test_resource_manager_discard_clears_sheetbook_plan_segments(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from scalim.sinks.rows import InMemoryRows
    from scalim.workflow import resources as resources_mod

    class _Instrumentation:
        def emit(self, event_type, payload, meta=None):  # type: ignore[no-untyped-def]
            return None

    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "mem": resources_mod.SheetBookDef(
                resource_id="mem",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
            )
        },
    )
    manager.apply_sheetbook_sheet(
        workflow_node_id="n0",
        decl_order=0,
        sheetbook_id="mem",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv=InMemoryRows(header=["id"], rows=[["a1"]]),
        on_conflict="error",
    )
    with caplog.at_level(logging.INFO, logger="scalim.workflow.resources"):
        manager.discard_all(workflow_node_id="n_discard", reason="workflow_failed")
    assert "mem" not in manager._sheetbooks  # noqa: SLF001
    assert "release_reason=discard" in caplog.text


def test_xlsx_memory_book_budget_policy_fail_fast_via_resources_policy(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl import (
        BookBudgetPolicy,
        BookResourcePolicy,
        ResourcesPolicy,
        WorkflowRunOptions,
        run_workflow,
    )
    from scalim.dsl.yaml_dsl.runtime.contracts import DemandRunOptions, DemandRunSecurityOptions

    demand = tmp_path / "d.yaml"
    demand.write_text(
        """
name: d
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources: {}
outputs:
  - name: detail
    to: {book: report, sheet: S1}
    fields: [order_id]
""".lstrip(),
        encoding="utf-8",
    )
    demand2 = tmp_path / "d2.yaml"
    demand2.write_text(
        """
name: d2
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources: {}
outputs:
  - name: detail
    to: {book: report, sheet: S2}
    fields: [order_id]
""".lstrip(),
        encoding="utf-8",
    )
    workflow = tmp_path / "wf.yaml"
    workflow.write_text(
        """
workflow:
  resources:
    books:
      report:
        xlsx_memory:
          export_xlsx: {path: ./out}
  runs:
    - id: a
      demand: ./d.yaml
    - id: b
      demand: ./d2.yaml
      depends_on: [a]
""".lstrip(),
        encoding="utf-8",
    )

    options = WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))),
        resources_policy=ResourcesPolicy(
            books={"report": BookResourcePolicy(budget=BookBudgetPolicy(max_sheets=1, max_total_cells=10000))}
        ),
    )
    with pytest.raises(Exception) as excinfo:
        _ = run_workflow(str(workflow), options=options)
    cause = excinfo.value.__cause__ or excinfo.value.__context__
    text = "{} {}".format(excinfo.value, cause)
    assert "budget" in text.lower() or "max_sheets" in text.lower() or "Sheetbook budget" in text


def test_xlsx_file_ignores_book_budget_policy(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl import (
        BookBudgetPolicy,
        BookResourcePolicy,
        ResourcesPolicy,
        WorkflowRunOptions,
        run_workflow,
    )
    from scalim.dsl.yaml_dsl.runtime.contracts import DemandRunOptions, DemandRunSecurityOptions

    demand = tmp_path / "d.yaml"
    demand.write_text(
        """
name: d
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources: {}
outputs:
  - name: detail
    to: {book: report, sheet: S1}
    fields: [order_id]
""".lstrip(),
        encoding="utf-8",
    )
    demand2 = tmp_path / "d2.yaml"
    demand2.write_text(
        """
name: d2
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources: {}
outputs:
  - name: detail
    to: {book: report, sheet: S2}
    fields: [order_id]
""".lstrip(),
        encoding="utf-8",
    )
    workflow = tmp_path / "wf.yaml"
    workflow.write_text(
        """
workflow:
  resources:
    books:
      report:
        xlsx_file:
          path: ./out
  runs:
    - id: a
      demand: ./d.yaml
    - id: b
      demand: ./d2.yaml
      depends_on: [a]
""".lstrip(),
        encoding="utf-8",
    )

    options = WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))),
        resources_policy=ResourcesPolicy(books={"report": BookResourcePolicy(budget=BookBudgetPolicy(max_sheets=1, max_total_cells=1))}),
    )
    result = run_workflow(str(workflow), options=options)
    assert all(o.error is None for o in result.outcomes)
