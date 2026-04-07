"""`workflow` 类型(稳定导入路径).

说明:
- 该模块提供更稳定、更明确的类型导入路径
- 当前实现仍位于 `workflow_config.py`,此处仅做 `re-export`
- 运行时需兼容 `Python 3.6`
"""

from typing import TYPE_CHECKING, Iterable, Optional, Tuple, Union, cast

from ...vendor.dataclassesx import dataclass
from .runtime.contracts import UNSET, DemandDiagnosticsOverride, RunOverrides, UnsetType
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
    from ...hooks import IExecutionHook
    from ...ob.observer import Observer


WorkflowComponent = Union["Observer", "IExecutionHook"]


@dataclass(frozen=True)
class ComponentsInherit:
    """继承 `run_workflow(..., options=RunOptions(components=[...]))` 的全局 `components` 列表用于本次运行."""


@dataclass(frozen=True)
class ComponentsReplace:
    """替换全局 `components` 列表(用 `items=()` 可显式禁用)."""

    items: Tuple[WorkflowComponent, ...] = ()

    def __post_init__(self) -> None:
        items_raw = self.items
        if not isinstance(items_raw, tuple):
            items_raw = tuple(cast("Iterable[WorkflowComponent]", items_raw))  # pragma: allow-cast components items normalization
        object.__setattr__(self, "items", items_raw)


@dataclass(frozen=True)
class ComponentsExtend:
    """在全局 `components` 列表后追加(保持顺序,不做隐式去重)."""

    items: Tuple[WorkflowComponent, ...] = ()

    def __post_init__(self) -> None:
        items_raw = self.items
        if not isinstance(items_raw, tuple):
            items_raw = tuple(cast("Iterable[WorkflowComponent]", items_raw))  # pragma: allow-cast components items normalization
        object.__setattr__(self, "items", items_raw)


ComponentsPatch = Union[ComponentsInherit, ComponentsReplace, ComponentsExtend]


@dataclass(frozen=True)
class WorkflowRunPatch:
    """用于 `run_workflow(..., run_patches_by_id=...)` 的单节点运行期补丁.

    三态约定:
    - `UNSET`: 继承 `run_workflow(..., options=RunOptions(...))` 的全局值
    - `None`: 显式禁用/清空(当字段支持时)
    - 非 `None`: 显式覆盖
    """

    batch_size: Union[Optional[int], UnsetType] = UNSET
    components: ComponentsPatch = ComponentsInherit()
    overrides: Union[Optional[RunOverrides], UnsetType] = UNSET
    guardrails: Union[Optional["GuardrailsPolicy"], UnsetType] = UNSET
    loader_retry: Union[Optional["LoaderRetryPoliciesSpec"], UnsetType] = UNSET
    demand_failure_policy: Union[Optional[str], UnsetType] = UNSET
    demand_diagnostics: Union[Optional[DemandDiagnosticsOverride], UnsetType] = UNSET


__all__ = (
    "UNSET",
    "ComponentsExtend",
    "ComponentsInherit",
    "ComponentsPatch",
    "ComponentsReplace",
    "ScalimWorkflowConfigError",
    "WorkflowCachePoolBudget",
    "WorkflowCachePoolOptions",
    "WorkflowCachePoolPin",
    "WorkflowConfig",
    "WorkflowOptions",
    "WorkflowOutputStagingOptions",
    "WorkflowResourcesWaitDiagnosticsOptions",
    "WorkflowResourcesWaitOptions",
    "WorkflowRun",
    "WorkflowRunPatch",
)
