"""Unit tests for FieldValue temporal types + expected-types label SSOT."""

from pathlib import Path

import pytest

from scalim.typedefs import FIELD_VALUE_TYPES, format_field_value_expected_types


def test_format_field_value_expected_types_tracks_field_value_types() -> None:
    label = format_field_value_expected_types()
    for typ in FIELD_VALUE_TYPES:
        assert typ.__name__ in label
    assert label.endswith("/None")
    assert "<class" not in label


def test_ensure_field_value_message_uses_dynamic_expected_label() -> None:
    from scalim.dsl.yaml_dsl.runtime.runtime_linking import _ensure_field_value

    expected = format_field_value_expected_types()
    with pytest.raises(TypeError) as exc_info:
        _ensure_field_value(object(), field_id="x", producer="call_by")
    msg = str(exc_info.value)
    assert "unsupported value type" in msg
    assert "expected {}".format(expected) in msg


def test_workflow_xlsx_aware_datetime_fails_like_openpyxl(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    from scalim.dsl.yaml_dsl import (
        DemandRunOptions,
        DemandRunSecurityOptions,
        WorkflowRunOptions,
        run_workflow,
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: aware_temporal

main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_table_aware_datetime"
  fields:
    created: {extract: created}

outputs:
  - name: detail
    to:
      book: report
      sheet: Types
    fields: [created]
""".lstrip(),
        encoding="utf-8",
    )
    out_root = tmp_path / "out"
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text(
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
""".format(out_root=str(out_root)).lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match=r"timezone"):
        _ = run_workflow(
            str(workflow),
            options=WorkflowRunOptions(
                demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.workflow_loaders"])))
            ),
        )
