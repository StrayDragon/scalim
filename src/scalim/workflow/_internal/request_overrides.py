from typing import Optional

from ...execution.run_ir import ExecutionRequest
from ...vendor.dataclassesx import dataclass, replace


@dataclass(frozen=True)
class WorkflowNodeRequestOverrides:
    capture_in_memory_rows: bool = False
    main_rows: Optional[object] = None


def merge_workflow_node_request(base_request: ExecutionRequest, overrides: WorkflowNodeRequestOverrides) -> ExecutionRequest:
    next_request = base_request
    if overrides.capture_in_memory_rows and not next_request.capture_in_memory_rows:
        next_request = replace(next_request, capture_in_memory_rows=True)
    if overrides.main_rows is not None:
        next_request = replace(next_request, main_rows=overrides.main_rows)
    return next_request


__all__ = []
