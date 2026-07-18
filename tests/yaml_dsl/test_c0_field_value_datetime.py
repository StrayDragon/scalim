"""c0: workflow xlsx preserves temporal FieldValues (no InMemoryRows str fallback)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunSecurityOptions,
    WorkflowRunOptions,
    run_workflow,
)
from scalim.execution import versioned_outputs


_ALLOWED = frozenset(["tests.fixtures.workflow_loaders"])


def _write(path: Path, text: str) -> Path:
    path.write_text(text.lstrip(), encoding="utf-8")
    return path


def _latest_book_path(out_root: Path, *, book_id: str) -> Path:
    latest = versioned_outputs.read_latest(out_root)
    version_id = latest.get("version_id")
    assert isinstance(version_id, str)
    return out_root / "versions" / version_id / "books" / "{}.xlsx".format(str(book_id))


def test_workflow_xlsx_preserves_naive_temporal_field_values(tmp_path: Path) -> None:
    fields = ["order_id", "created", "day", "clock", "span", "label"]
    field_lines = "\n".join("    {}: {{extract: {}}}".format(f, f) for f in fields)
    _write(
        tmp_path / "demand.yaml",
        """
name: temporal

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_table_temporal_values"
  fields:
{fields}

outputs:
  - name: detail
    to:
      book: report
      sheet: Types
    fields: {field_list}
""".format(
            fields=field_lines,
            field_list=fields,
        ),
    )
    out_root = tmp_path / "out"
    _write(
        tmp_path / "workflow.yaml",
        """
workflow:
  resources:
    books:
      report:
        xlsx:
          path: "{out_root}"
  runs:
    - id: a
      demand: ./demand.yaml
""".format(out_root=str(out_root)),
    )

    result = run_workflow(
        str(tmp_path / "workflow.yaml"),
        options=WorkflowRunOptions(demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=_ALLOWED))),
    )
    assert not result.errors()

    book_path = _latest_book_path(out_root, book_id="report")
    wb = openpyxl.load_workbook(str(book_path), data_only=False)
    try:
        ws = wb["Types"]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        assert headers == fields
        cells = list(next(ws.iter_rows(min_row=2, max_row=2)))
        by_name = {headers[i]: cells[i] for i in range(len(headers))}

        assert by_name["order_id"].value == 1001
        assert by_name["order_id"].data_type == "n"
        assert by_name["label"].value == "ok"

        assert by_name["created"].data_type == "d"
        assert isinstance(by_name["created"].value, datetime)
        assert not isinstance(by_name["created"].value, str)

        assert by_name["day"].data_type == "d"
        assert isinstance(by_name["day"].value, (datetime, date))
        assert not isinstance(by_name["day"].value, str)

        assert by_name["clock"].data_type == "d"
        assert isinstance(by_name["clock"].value, time)
        assert by_name["span"].data_type == "d"
        assert isinstance(by_name["span"].value, timedelta)
    finally:
        wb.close()
