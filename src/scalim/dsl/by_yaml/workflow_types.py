"""`workflow` types(稳定导入路径).

说明:
- 该模块提供更稳定、更明确的类型导入路径
- 当前实现仍位于 `workflow_config.py`,此处仅做 `re-export`
- 运行时需兼容 `Python 3.6`
"""

from typing import TYPE_CHECKING, Optional, Tuple, Union

from ...vendor.dataclassesx import dataclass

from .runtime.contracts import UNSET, RunOverrides, UnsetType
from .workflow_config import (
    ScalimWorkflowConfigError,
    WorkflowCachePoolBudget,
    WorkflowCachePoolOptions,
    WorkflowCachePoolPin,
    WorkflowConfig,
    WorkflowOptions,
    WorkflowOutputStagingOptions,
    WorkflowResourcesWaitDiagnosticsOptions,
    WorkflowResourcesWaitOptions,
    WorkflowRun,
)

if TYPE_CHECKING:
    from ...execution.guardrails import GuardrailsPolicy
    from ...execution.loader_retry import LoaderRetryPoliciesSpec


@dataclass(frozen=True)
class ComponentsInherit:
    """Inherit `run_workflow(..., components=...)` global components for this run."""


@dataclass(frozen=True)
class ComponentsReplace:
    """Replace global components for this run (use `items=()` to explicitly disable)."""

    items: Tuple[object, ...] = ()

    def __post_init__(self) -> None:
        items_raw = self.items
        if not isinstance(items_raw, tuple):
            items_raw = tuple(items_raw)
        object.__setattr__(self, "items", items_raw)


@dataclass(frozen=True)
class ComponentsExtend:
    """Append per-run components after global components (order-preserving, no implicit de-dup)."""

    items: Tuple[object, ...] = ()

    def __post_init__(self) -> None:
        items_raw = self.items
        if not isinstance(items_raw, tuple):
            items_raw = tuple(items_raw)
        object.__setattr__(self, "items", items_raw)


ComponentsPatch = Union[ComponentsInherit, ComponentsReplace, ComponentsExtend]


@dataclass(frozen=True)
class WorkflowRunPatch:
    """Per-run runtime patch for `run_workflow(..., run_patches_by_id=...)`.

    Tri-state conventions:
    - `UNSET`: inherit the corresponding `run_workflow(...)` global value
    - `None`: explicit disable/clear (when supported)
    - non-`None`: explicit override
    """

    batch_size: Union[Optional[int], UnsetType] = UNSET
    components: ComponentsPatch = ComponentsInherit()
    overrides: Union[Optional[RunOverrides], UnsetType] = UNSET
    guardrails: Union[Optional["GuardrailsPolicy"], UnsetType] = UNSET
    loader_retry: Union[Optional["LoaderRetryPoliciesSpec"], UnsetType] = UNSET
    demand_failure_policy: Union[Optional[str], UnsetType] = UNSET


__all__ = (
    "ComponentsExtend",
    "ComponentsInherit",
    "ComponentsPatch",
    "ComponentsReplace",
    "ScalimWorkflowConfigError",
    "UNSET",
    "WorkflowCachePoolBudget",
    "WorkflowCachePoolOptions",
    "WorkflowCachePoolPin",
    "WorkflowConfig",
    "WorkflowOptions",
    "WorkflowOutputStagingOptions",
    "WorkflowResourcesWaitDiagnosticsOptions",
    "WorkflowResourcesWaitOptions",
    "WorkflowRunPatch",
    "WorkflowRun",
)
