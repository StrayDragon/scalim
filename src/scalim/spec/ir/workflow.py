from enum import Enum
from typing import Dict, Optional, Tuple, Union

from ...vendor.dataclassesx import dataclass, field


class WorkflowNodeType(str, Enum):
    DEMAND = "demand"
    WRITE_SHEET = "write_sheet"
    APPEND_SHEET = "append_sheet"
    CONDITION = "condition"
    SELECTOR = "selector"


@dataclass(frozen=True)
class WorkflowResourceIr:
    resource_id: str
    resource_type: str
    path: str
    options: Optional[Dict[str, object]] = None


@dataclass(frozen=True)
class WorkflowNodeIr:
    node_id: str
    node_type: WorkflowNodeType
    decl_order: int
    deps: Tuple[str, ...] = ()
    demand_path: Optional[str] = None
    init_vars: Optional[Dict[str, object]] = None


@dataclass(frozen=True)
class WorkflowDemandNodeDerivedIr:
    workbook_output_paths_abs: Tuple[str, ...] = ()
    workflow_managed_csv_output_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class WriteSheetNodeIr:
    node_id: str
    node_type: WorkflowNodeType
    decl_order: int
    deps: Tuple[str, ...] = ()
    resource_type: str = ""
    resource_id: str = ""
    sheet: str = ""
    input_node_id: str = ""
    input_output_id: str = ""
    on_conflict: str = "error"


@dataclass(frozen=True)
class AppendSheetNodeIr:
    node_id: str
    node_type: WorkflowNodeType
    decl_order: int
    deps: Tuple[str, ...] = ()
    resource_type: str = ""
    resource_id: str = ""
    sheet: Optional[str] = None
    input_node_id: str = ""
    input_output_id: str = ""
    align_by: str = "field_id"
    header_policy: str = "once"
    on_mismatch: str = "error"


@dataclass(frozen=True)
class WorkflowEdgeIr:
    from_node_id: str
    to_node_id: str


@dataclass(frozen=True)
class WorkflowCachePoolBudgetIr:
    max_entries: int
    over_budget_policy: str


@dataclass(frozen=True)
class WorkflowCachePoolPinIr:
    kind: str
    source_id: str


@dataclass(frozen=True)
class WorkflowCachePoolIr:
    conflict_policy: str
    release_policy: str
    budget: WorkflowCachePoolBudgetIr
    pin: Tuple[WorkflowCachePoolPinIr, ...] = ()


@dataclass(frozen=True)
class WorkflowCtxOptionsIr:
    max_value_bytes: int = 65536
    max_bytes: int = 1048576


@dataclass(frozen=True)
class WorkflowOptionsIr:
    max_concurrency: int = 1
    failure_policy: str = "all_fail"
    cache_pool: Optional[WorkflowCachePoolIr] = None
    ctx: WorkflowCtxOptionsIr = field(default_factory=WorkflowCtxOptionsIr)


@dataclass(frozen=True)
class WorkflowArtifactsIr:
    slots_by_node_id: Dict[str, Tuple[str, ...]]


WorkflowAnyNodeIr = Union[WorkflowNodeIr, WriteSheetNodeIr, AppendSheetNodeIr]


@dataclass(frozen=True)
class WorkflowIr:
    nodes: Tuple[WorkflowAnyNodeIr, ...]
    edges: Tuple[WorkflowEdgeIr, ...]
    options: WorkflowOptionsIr
    resources: Tuple[WorkflowResourceIr, ...]
    artifacts: WorkflowArtifactsIr
