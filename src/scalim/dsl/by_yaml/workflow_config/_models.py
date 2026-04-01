from typing import Dict, Optional, Tuple

from ....vendor.dataclassesx import dataclass
from ....vendor.dataclassesx import field as dataclass_field
from ..schema_dsl.models import ResourcesConfig


@dataclass(frozen=True)
class WorkflowRun:
    id: str
    demand: str
    depends_on: Tuple[str, ...] = ()
    main_rows_from_run_id: Optional[str] = None
    init_vars: Optional[Dict[str, object]] = None


@dataclass(frozen=True)
class WorkflowCtxOptions:
    max_value_bytes: int = 65536
    max_bytes: int = 1048576


@dataclass(frozen=True)
class WorkflowCachePoolBudget:
    max_entries: int
    over_budget_policy: str


@dataclass(frozen=True)
class WorkflowCachePoolPin:
    kind: str
    source_id: str


@dataclass(frozen=True)
class WorkflowCachePoolOptions:
    conflict_policy: str
    release_policy: str
    budget: WorkflowCachePoolBudget
    pin: Tuple[WorkflowCachePoolPin, ...] = ()


@dataclass(frozen=True)
class WorkflowResourcesWaitDiagnosticsOptions:
    enabled: bool = False
    warn_after_s: float = 30.0
    repeat_every_s: Optional[float] = None
    capture_owner_callsite: bool = False


@dataclass(frozen=True)
class WorkflowResourcesWaitOptions:
    max_wait_s: float = 600.0
    diagnostics: WorkflowResourcesWaitDiagnosticsOptions = dataclass_field(default_factory=WorkflowResourcesWaitDiagnosticsOptions)


@dataclass(frozen=True)
class WorkflowOutputStagingOptions:
    dir_name: str = ".scalim-staging"
    keep_on_success: bool = False
    keep_on_failure: bool = True


@dataclass(frozen=True)
class WorkflowOptions:
    max_concurrency: int = 1
    failure_policy: str = "all_fail"
    cache_pool: Optional[WorkflowCachePoolOptions] = None
    ctx: WorkflowCtxOptions = dataclass_field(default_factory=WorkflowCtxOptions)
    resources_wait: WorkflowResourcesWaitOptions = dataclass_field(default_factory=WorkflowResourcesWaitOptions)
    output_staging: WorkflowOutputStagingOptions = dataclass_field(default_factory=WorkflowOutputStagingOptions)


@dataclass(frozen=True)
class WorkflowConfig:
    runs: Tuple[WorkflowRun, ...]
    options: WorkflowOptions
    resources: ResourcesConfig = dataclass_field(default_factory=ResourcesConfig)


__all__ = []
