"""`workflow` 类型(稳定导入路径).

说明:
- 该模块提供更稳定、更明确的类型导入路径
- 当前实现仍位于 `workflow_config.py`,此处仅做 `re-export`
- 运行时需兼容 `Python 3.6`
"""

from typing import TYPE_CHECKING, Iterable, Mapping, Optional, Tuple, Union, cast

from ...vendor.dataclassesx import dataclass
from ...vendor.dataclassesx import field as dataclass_field
from .book_resource_policy import ResourcesPolicy
from .runtime.contracts import UNSET, DemandDiagnosticsOverride, DemandRunOptions, RunOverrides, UnsetType
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
    """继承 `WorkflowRunOptions.demand.runtime.components` 的全局 `components` 列表用于本次运行."""


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
class WorkflowNodePatch:
    """用于 `WorkflowRunOptions.patches_by_run_id` 的单节点运行期补丁.

    三态约定:
    - `UNSET`: 继承 `WorkflowRunOptions.demand` 的全局值
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


_WORKFLOW_CACHE_POOL_PIN_KINDS = frozenset(("preload_forever",))
_WORKFLOW_CACHE_POOL_PIN_KINDS_LABEL = "preload_forever"


@dataclass(frozen=True)
class WorkflowCachePoolPin:
    kind: str
    source_id: str

    def __post_init__(self) -> None:
        kind_raw = self.kind
        if not isinstance(kind_raw, str):
            msg = "WorkflowCachePoolPin.kind must be a str"
            raise TypeError(msg)
        normalized_kind = kind_raw.strip().lower().replace("-", "_")
        if not normalized_kind:
            msg = "WorkflowCachePoolPin.kind must not be empty; expected one of: {}".format(_WORKFLOW_CACHE_POOL_PIN_KINDS_LABEL)
            raise ValueError(msg)
        if normalized_kind not in _WORKFLOW_CACHE_POOL_PIN_KINDS:
            msg = "WorkflowCachePoolPin.kind must be one of: {} (got {!r})".format(_WORKFLOW_CACHE_POOL_PIN_KINDS_LABEL, kind_raw)
            raise ValueError(msg)
        object.__setattr__(self, "kind", str(normalized_kind))

        source_id_raw = self.source_id
        if not isinstance(source_id_raw, str):
            msg = "WorkflowCachePoolPin.source_id must be a str"
            raise TypeError(msg)
        normalized_source_id = str(source_id_raw).strip()
        if not normalized_source_id:
            msg = "WorkflowCachePoolPin.source_id must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "source_id", normalized_source_id)


@dataclass(frozen=True)
class WorkflowCachePoolDisabled(WorkflowCachePoolPreset):
    """禁用工作流级 `cache pool`(默认)."""


@dataclass(frozen=True)
class WorkflowCachePoolPreloadForeverUnlimited(WorkflowCachePoolPreset):
    """启用跨节点共享 `preload_forever` 缓存条目(不施加条目数量预算)."""


@dataclass(frozen=True)
class WorkflowCachePoolPreloadForeverShared(WorkflowCachePoolPreset):
    """启用跨节点共享 `preload_forever` 缓存条目(仅暴露最小必要参数)."""

    max_entries: int
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


@dataclass(frozen=True)
class WorkflowRunOptions:
    """`workflow` 官方运行入口(`run_workflow`)的 `options` 契约."""

    demand: DemandRunOptions
    """每个节点默认使用的 `demand` `options`(`SSOT`)."""

    patches_by_run_id: Optional[Mapping[str, WorkflowNodePatch]] = None
    """可选:按 `run_id` 的补丁(作用于节点的 `demand` `options` 子集)."""

    runtime: WorkflowRuntimeOptions = dataclass_field(default_factory=WorkflowRuntimeOptions.preset_default)
    """可选:`workflow` 编排策略(调度/并发/资源等待等)."""

    path_aliases: Optional[Mapping[str, str]] = None
    """可选:`workflow` 解析 `demand` 路径的别名表."""

    workflow_components: Optional[Tuple[WorkflowComponent, ...]] = None
    """可选:`workflow` 编排层观测组件(不作用于单个 `demand` 执行)."""

    resources_policy: Optional["ResourcesPolicy"] = None
    """可选:`book` 写入策略与预算(`Python` `SSOT`;缺省 `builtin` `defaults`)."""

    def __post_init__(self) -> None:
        if not isinstance(self.demand, DemandRunOptions):
            msg = "WorkflowRunOptions.demand must be a DemandRunOptions"
            raise TypeError(msg)

        if self.patches_by_run_id is not None and not isinstance(self.patches_by_run_id, Mapping):
            msg = "WorkflowRunOptions.patches_by_run_id must be a mapping from run_id to WorkflowNodePatch"
            raise TypeError(msg)

        aliases = self.path_aliases
        if aliases is not None and not isinstance(aliases, Mapping):
            msg = "WorkflowRunOptions.path_aliases must be a mapping"
            raise TypeError(msg)

        comps = self.workflow_components
        if comps is not None and not isinstance(comps, tuple):
            object.__setattr__(
                self,
                "workflow_components",
                tuple(cast("Iterable[WorkflowComponent]", comps)),  # pragma: allow-cast components normalization boundary
            )

        if self.resources_policy is not None and not isinstance(self.resources_policy, ResourcesPolicy):
            msg = "WorkflowRunOptions.resources_policy must be a ResourcesPolicy or None"
            raise TypeError(msg)


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
    "WorkflowCachePoolPreloadForeverUnlimited",
    "WorkflowCachePoolPreset",
    "WorkflowConfig",
    "WorkflowExecutionOptions",
    "WorkflowNodePatch",
    "WorkflowOutputStagingOptions",
    "WorkflowResourcesWaitDiagnosticsOptions",
    "WorkflowResourcesWaitOptions",
    "WorkflowRun",
    "WorkflowRunOptions",
    "WorkflowRuntimeOptions",
)
