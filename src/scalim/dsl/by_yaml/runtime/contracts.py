from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, Tuple, Union, cast

from ....execution.guardrails import GuardrailsPolicy
from ....execution.loader_retry import LoaderRetryPoliciesSpec
from ....execution.run_ir import ExecutionResult
from ....hooks.base import IExecutionHook
from ....ob.observer import Observer
from ....sinks.sink_base import ISink
from ....typedefs import ParallelMode
from ....vendor.compact.importlibx import import_module
from ....vendor.compact.typing_extensionsx import override
from ..schema_dsl.models import DemandConfig

if TYPE_CHECKING:
    import pandas as pd

    from ....execution.output_composition import OutputCompositionSpec
    from ....execution.run_ir import ExecutionRequest
    from ....ob.presets.viz import VizObserverConfig
    from ....planning.plan import ExecutionPlan
    from ....spec.ir.demand import DemandIr


class _UnsetType:
    __slots__: Tuple[str, ...] = ()

    @override
    def __repr__(self) -> str:
        return "UNSET"


UNSET = _UnsetType()


@dataclass(frozen=True)
class OutputOverrides:
    """`YAML` 的 `output` 配置段覆盖项.

    - 任意字段设为 `UNSET` 表示“不覆盖 `YAML` 配置”.
    - 某些字段(例如 `path`/`fields`)允许显式使用 `None` 表示“禁用/清空”.
    """

    format: Union[str, _UnsetType] = UNSET
    path: Union[Optional[str], _UnsetType] = UNSET
    encoding: Union[str, _UnsetType] = UNSET
    streaming: Union[bool, _UnsetType] = UNSET
    include_header: Union[bool, _UnsetType] = UNSET
    header_fields_output_by: Union[str, _UnsetType] = UNSET
    fields: Union[Optional[List[str]], _UnsetType] = UNSET


@dataclass(frozen=True)
class RunOverrides:
    output: OutputOverrides = dataclass_field(default_factory=OutputOverrides)
    viz_config: Union[Optional["VizObserverConfig"], _UnsetType] = UNSET


@dataclass(frozen=True)
class RunOptions:
    allowed_modules: FrozenSet[str]
    """允许被引用/导入的模块白名单(用于安全解析)."""

    allowed_functions: Optional[FrozenSet[str]] = None
    """可选:允许被引用/导入的函数白名单(用于更细粒度的安全控制)."""

    components: Optional[List[Union[Observer, IExecutionHook]]] = None
    """可选:要挂载的 `Observer`/`Hook` 组件列表."""

    sink: Optional[ISink] = None
    """可选:显式指定输出端;若为 `None` 则按配置创建."""

    output_composition: Optional["OutputCompositionSpec"] = None
    """可选:多输出组合请求(`IR/Python-only`).当提供该字段时,运行期会忽略 YAML 的单输出装配."""

    guardrails: Optional[GuardrailsPolicy] = None
    """可选:运行时护栏策略."""

    loader_retry: Optional[LoaderRetryPoliciesSpec] = None
    """可选:加载重试策略规范."""

    batch_size: Optional[int] = None
    """可选:覆盖批大小(`None` 表示不覆盖)."""

    parallel_mode: ParallelMode = "seq"
    """并行模式(`seq` 或 `adaptive`)."""

    max_workers: int = 0
    """最大并发工作数提示(`0` 表示自动)."""

    overrides: Optional[RunOverrides] = None
    """可选:运行期覆盖项(例如输出与 `viz` 配置覆盖)."""

    runtime_vars: Optional[Dict[str, object]] = None
    """可选:运行期变量注入(编译期使用,用于解析 `$runtime.*` 占位符)."""


@dataclass(frozen=True)
class Compilation:
    config: DemandConfig
    demand_ir: "DemandIr"
    request: "ExecutionRequest"


class RunResult:
    core: ExecutionResult
    config: DemandConfig
    yaml_path: str
    sink: Optional[ISink]

    def __init__(
        self,
        core: ExecutionResult,
        *,
        config: DemandConfig,
        yaml_path: str,
        sink: Optional[ISink] = None,
    ) -> None:
        self.core = core
        self.config = config
        self.yaml_path = yaml_path
        self.sink = sink

    @property
    def output_path(self) -> Optional[str]:
        return self.core.output_path

    @property
    def total_rows(self) -> int:
        return self.core.total_rows

    @property
    def duration(self) -> float:
        return self.core.duration

    @property
    def demand_ir(self) -> "DemandIr":
        return self.core.demand_ir

    @property
    def plan(self) -> "ExecutionPlan":
        return self.core.plan

    def to_dataframe(self) -> "pd.DataFrame":
        sink = self.sink
        if sink is None or not hasattr(sink, "get_data"):
            msg = "to_dataframe() requires an in-memory sink with get_data() (e.g. InMemoryRowSink)"
            raise ValueError(msg)
        try:
            pd = import_module("pandas")
            return pd.DataFrame(cast("Any", sink).get_data())  # type: ignore[no-any-return]
        except ImportError as e:
            msg = "pandas is required for to_dataframe()"
            raise ImportError(msg) from e


__all__ = [
    "UNSET",
    "Compilation",
    "OutputOverrides",
    "RunOptions",
    "RunOverrides",
    "RunResult",
]
