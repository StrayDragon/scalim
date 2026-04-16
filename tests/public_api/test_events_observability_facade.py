import pytest

from scalim.events import (
    EventType,
    WorkflowNodeCancelledReason,
    WorkflowNodeEndStatus,
    get_event_catalog,
    get_event_catalog_map,
)
from scalim.ob import ObservabilityOptions


def test_event_type_values_are_stable() -> None:
    assert EventType.PIPELINE_START.value == "pipeline_start"
    assert EventType.PIPELINE_END.value == "pipeline_end"
    assert EventType.LOADER_CALL.value == "loader_call"
    assert EventType.ERROR.value == "error"
    assert EventType.WORKFLOW_NODE_START.value == "workflow_node_start"
    assert EventType.WORKFLOW_NODE_END.value == "workflow_node_end"
    assert EventType.PRE_USE_BATCH_SIZE.value == "pre_use_batch_size"

    assert str(EventType.PIPELINE_START) == "pipeline_start"


def test_workflow_event_enums_keep_existing_values() -> None:
    assert WorkflowNodeEndStatus.OK.value == "ok"
    assert WorkflowNodeEndStatus.ERROR.value == "error"
    assert str(WorkflowNodeEndStatus.OK) == "ok"

    assert WorkflowNodeCancelledReason.DEPENDENCY_FAILED.value == "dependency_failed"
    assert WorkflowNodeCancelledReason.UPSTREAM_CANCELLED.value == "upstream_cancelled"
    assert WorkflowNodeCancelledReason.POLICY_ALL_FAIL.value == "policy_all_fail"


def test_event_catalog_works_with_event_type_enum_members() -> None:
    catalog = get_event_catalog()
    assert catalog

    catalog_map = get_event_catalog_map()
    assert EventType.PIPELINE_START in catalog_map
    assert EventType.PIPELINE_END in catalog_map

    assert catalog_map[EventType.PIPELINE_START].name == "pipeline_start"


def test_observability_options_validation_is_fail_fast() -> None:
    with pytest.raises(ValueError, match=r"ObservabilityOptions\.loader_result_policy"):
        ObservabilityOptions(loader_result_policy="bogus")

    with pytest.raises(ValueError, match=r"ObservabilityOptions\.loader_result_sample_size"):
        ObservabilityOptions(loader_result_sample_size=0)


def test_observability_options_normalizes_fields() -> None:
    opts = ObservabilityOptions(loader_result_policy="FULL", loader_result_sample_size=2.0)
    assert opts.loader_result_policy == "full"
    assert opts.loader_result_sample_size == 2


def test_event_type_group_view_is_importable() -> None:
    from scalim.events import type_groups

    assert type_groups.pipeline.start == EventType.PIPELINE_START
    assert type_groups.loader.call == EventType.LOADER_CALL
    assert type_groups.workflow.node.start == EventType.WORKFLOW_NODE_START
