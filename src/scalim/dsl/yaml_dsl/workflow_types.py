"""`workflow` 类型(稳定导入路径).

说明:
- 该模块提供更稳定、更明确的类型导入路径
- 当前实现仍位于 `workflow_config.py`,此处仅做 `re-export`
- 运行时需兼容 `Python 3.6`
"""

from typing import TYPE_CHECKING, Iterable, Optional, Tuple, Union, cast

from ...vendor.dataclassesx import dataclass
from ...vendor.dataclassesx import field as dataclass_field
from .runtime.contracts import UNSET, DemandDiagnosticsOverride, RunOverrides, UnsetType
from .workflow_config import (
    ScalimWorkflowConfigError,
    WorkflowConfig,
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
class WorkflowRunOptionsPatch:
    """用于 `run_workflow(..., run_options_patches_by_run_id=...)` 的单节点运行期补丁.

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
    parallel_mode: Union[str, UnsetType] = UNSET
    max_workers: Union[int, UnsetType] = UNSET


@dataclass(frozen=True)
class WorkflowExecutionOptions:
    """工作流运行期编排策略(与环境相关; 运行期策略边界)."""

    max_concurrency: int = 1
    failure_policy: str = "all_fail"


class WorkflowCachePoolPreset:
    """工作流级 `cache pool` 的对外配置入口(封闭集合; 仅允许预设)."""


@dataclass(frozen=True)
class WorkflowCachePoolPin:
    kind: str
    source_id: str


@dataclass(frozen=True)
class WorkflowCachePoolDisabled(WorkflowCachePoolPreset):
    """禁用工作流级 `cache pool`(默认)."""


@dataclass(frozen=True)
class WorkflowCachePoolPreloadForeverShared(WorkflowCachePoolPreset):
    """启用跨节点共享 `preload_forever` 缓存条目(仅暴露最小必要参数)."""

    max_entries: int = 16
    pin: Tuple[WorkflowCachePoolPin, ...] = ()


@dataclass(frozen=True)
class PipelineSchedulerOptions:
    """默认调度策略: `DAG` 流水线(节点就绪即运行)."""


@dataclass(frozen=True)
class StageBarrierSchedulerOptions:
    """阶段屏障调度策略: 下一阶段必须等待上一阶段全部终态后才可启动."""


@dataclass(frozen=True)
class WorkflowRuntimeOptions:
    """工作流运行期策略对象(正交组织; 避免大平铺)."""

    execution: WorkflowExecutionOptions = dataclass_field(default_factory=WorkflowExecutionOptions)
    cache_pool: WorkflowCachePoolPreset = dataclass_field(default_factory=WorkflowCachePoolDisabled)
    resources_wait: WorkflowResourcesWaitOptions = dataclass_field(default_factory=WorkflowResourcesWaitOptions)
    output_staging: WorkflowOutputStagingOptions = dataclass_field(default_factory=WorkflowOutputStagingOptions)
    scheduler: Union[PipelineSchedulerOptions, StageBarrierSchedulerOptions] = dataclass_field(default_factory=PipelineSchedulerOptions)

    @classmethod
    def preset_default(cls) -> "WorkflowRuntimeOptions":
        return cls()


__all__ = (
    "UNSET",
    "ComponentsExtend",
    "ComponentsInherit",
    "ComponentsPatch",
    "ComponentsReplace",
    "PipelineSchedulerOptions",
    "ScalimWorkflowConfigError",
    "StageBarrierSchedulerOptions",
    "WorkflowCachePoolDisabled",
    "WorkflowCachePoolPin",
    "WorkflowCachePoolPreloadForeverShared",
    "WorkflowCachePoolPreset",
    "WorkflowConfig",
    "WorkflowExecutionOptions",
    "WorkflowOutputStagingOptions",
    "WorkflowResourcesWaitDiagnosticsOptions",
    "WorkflowResourcesWaitOptions",
    "WorkflowRun",
    "WorkflowRunOptionsPatch",
    "WorkflowRuntimeOptions",
)
