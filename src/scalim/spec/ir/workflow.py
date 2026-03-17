from dataclasses import dataclass
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


@dataclass(frozen=True)
class WorkflowEdgeIr:
    from_node_id: str
    to_node_id: str


@dataclass(frozen=True)
class WorkflowOptionsIr:
    max_concurrency: int = 1
    failure_policy: str = "all_fail"
    share_preload_cache: bool = False


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
