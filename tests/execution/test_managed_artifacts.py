import pytest

from scalim.execution.managed_artifacts import ManagedArtifactPlan, create_managed_artifact_sink
from scalim.execution.output_contracts import ExportLayout, OutputSpec


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
