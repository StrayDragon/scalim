import pytest

from scalim.execution.managed_artifacts import (
    MANAGED_ARTIFACT_KIND_CSV,
    MANAGED_ARTIFACT_KIND_ROWS,
    ManagedArtifactPlan,
    create_managed_artifact_sink,
)
from scalim.execution.output_contracts import ExportLayout, OutputSpec
from scalim.execution.run_ir import _collect_managed_artifact_outputs
from scalim.sinks.rows import in_memory_rows_to_in_memory_csv


def test_managed_artifact_plan_to_csv_artifact_returns_none_without_sink() -> None:
    plan = ManagedArtifactPlan(kind="csv")
    assert plan.to_csv_artifact() is None


def test_create_managed_artifact_sink_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unsupported managed artifact kind"):
        _ = create_managed_artifact_sink(
            target_id="detail",
            fmt="csv",
            layout=ExportLayout(field_ids=("id",)),
            output=OutputSpec(format="csv", streaming=True),
            managed_artifact_kind="weird",
        )


def test_collect_managed_artifact_outputs_skips_csv_copy_for_rows_plans() -> None:
    rows_sink, rows_plan = create_managed_artifact_sink(
        target_id="detail",
        fmt="excel",
        layout=ExportLayout(field_ids=("id", "amount")),
        output=OutputSpec(format="excel", streaming=True),
        managed_artifact_kind=MANAGED_ARTIFACT_KIND_ROWS,
    )
    rows_sink.write_row({"id": 1, "amount": 2.5})
    rows_sink.close()

    csv_sink, csv_plan = create_managed_artifact_sink(
        target_id="csv_out",
        fmt="csv",
        layout=ExportLayout(field_ids=("id",)),
        output=OutputSpec(format="csv", streaming=True),
        managed_artifact_kind=MANAGED_ARTIFACT_KIND_CSV,
    )
    csv_sink.write_row({"id": "x"})
    csv_sink.close()

    rows_map, csv_map = _collect_managed_artifact_outputs({"detail": rows_plan, "csv_out": csv_plan})
    assert rows_map is not None and "detail" in rows_map
    assert csv_map is not None and "csv_out" in csv_map
    assert "detail" not in csv_map

    # Explicit utility / plan conversion remains available even though collect does not call it.
    converted = in_memory_rows_to_in_memory_csv(rows_map["detail"])
    assert converted.header == ["id", "amount"]
    assert converted.rows == [["1", "2.5"]]
    assert rows_plan.to_csv_artifact() is not None
