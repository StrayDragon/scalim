from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class WorkflowNodeType(str, Enum):
    DEMAND = "demand"
    WRITE_SHEET = "write_sheet"
    APPEND_SHEET = "append_sheet"
    CONDITION = "condition"
    SELECTOR = "selector"


@dataclass(frozen=True)
class WorkflowNodeIr:
    node_id: str
    node_type: WorkflowNodeType
    decl_order: int
    deps: Tuple[str, ...] = ()
    demand_path: Optional[str] = None
    init_vars: Optional[Dict[str, object]] = None


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


@dataclass(frozen=True)
class WorkflowIr:
    nodes: Tuple[WorkflowNodeIr, ...]
    edges: Tuple[WorkflowEdgeIr, ...]
    options: WorkflowOptionsIr
    resources: Dict[str, object]
    artifacts: WorkflowArtifactsIr
