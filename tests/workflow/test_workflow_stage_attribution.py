from scalim.spec.ir._workflow import (
    WorkflowArtifactsIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
    WriteSheetNodeIr,
)
from scalim.workflow.stage_attribution import derive_workflow_struct_levels, derive_workflow_user_stages


def test_workflow_user_stage_does_not_fold_write_node_without_input_node_id() -> None:
    node_a = WorkflowNodeIr(
        node_id="a",
        node_type=WorkflowNodeType.DEMAND,
        decl_order=0,
        deps=(),
        demand_path="a.yaml",
    )
    write_node = WriteSheetNodeIr(
        node_id="w",
        node_type=WorkflowNodeType.WRITE_SHEET,
        decl_order=1,
        deps=("a",),
        resource_type="excel",
        resource_id="book",
        sheet="Sheet1",
        input_node_id="",
        input_output_id="out",
        on_conflict="error",
    )
    workflow_ir = WorkflowIr(
        nodes=(node_a, write_node),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )

    struct_levels = derive_workflow_struct_levels(workflow_ir)
    stages = derive_workflow_user_stages(workflow_ir, struct_levels=struct_levels)

    assert struct_levels["a"] == 0
    assert struct_levels["w"] == 1
    assert stages["w"] == 1
