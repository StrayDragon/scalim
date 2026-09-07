from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    options: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkflowNodeIr:
    node_id: str
    node_type: WorkflowNodeType
    decl_order: int
    deps: tuple[str, ...] = ()
    demand_path: str | None = None
    init_vars: dict[str, Any] | None = None
    main_rows_from_run_id: str | None = None


@dataclass(frozen=True)
class WorkflowDemandNodeDerivedIr:
    workbook_output_paths_abs: tuple[str, ...] = ()
    workflow_managed_csv_output_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class WriteSheetNodeIr:
    node_id: str
    node_type: WorkflowNodeType
    decl_order: int
    deps: tuple[str, ...] = ()
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
    deps: tuple[str, ...] = ()
    resource_type: str = ""
    resource_id: str = ""
    sheet: str | None = None
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
    budget: WorkflowCachePoolBudgetIr | None = None
    pin: tuple[WorkflowCachePoolPinIr, ...] = ()


@dataclass(frozen=True)
class WorkflowResourcesWaitDiagnosticsIr:
    enabled: bool = False
    warn_after_s: float = 30.0
    repeat_every_s: float | None = None
    capture_owner_callsite: bool = False


@dataclass(frozen=True)
class WorkflowResourcesWaitOptionsIr:
    max_wait_s: float = 600.0
    diagnostics: WorkflowResourcesWaitDiagnosticsIr = field(default_factory=WorkflowResourcesWaitDiagnosticsIr)


@dataclass(frozen=True)
class WorkflowOutputStagingOptionsIr:
    dir_name: str = ".scalim-staging"
    keep_on_success: bool = False
    keep_on_failure: bool = True


@dataclass(frozen=True)
class WorkflowOptionsIr:
    max_concurrency: int = 1
    failure_policy: str = "all_fail"
    schedule_mode: str = "pipeline"
    cache_pool: WorkflowCachePoolIr | None = None
    resources_wait: WorkflowResourcesWaitOptionsIr = field(default_factory=WorkflowResourcesWaitOptionsIr)
    output_staging: WorkflowOutputStagingOptionsIr = field(default_factory=WorkflowOutputStagingOptionsIr)


@dataclass(frozen=True)
class WorkflowArtifactsIr:
    slots_by_node_id: dict[str, tuple[str, ...]]


WorkflowAnyNodeIr = WorkflowNodeIr | WriteSheetNodeIr | AppendSheetNodeIr


@dataclass(frozen=True)
class WorkflowIr:
    nodes: tuple[WorkflowAnyNodeIr, ...]
    edges: tuple[WorkflowEdgeIr, ...]
    options: WorkflowOptionsIr
    resources: tuple[WorkflowResourceIr, ...]
    artifacts: WorkflowArtifactsIr


__all__ = ()
