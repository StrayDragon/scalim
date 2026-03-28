from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Mapping, Optional, Tuple, Union, cast

from ....execution.guardrails import GuardrailsPolicy
from ....execution.loader_retry import LoaderRetryPoliciesSpec
from ....execution.run_ir import ExecutionResult
from ....hooks import IExecutionHook
from ....ob.observer import Observer
from ....sinks import ISink
from ....typedefs import KeyNormalizationMode, ParallelMode
from ....vendor.compact.importlibx import import_module
from ....vendor.compact.typing_extensionsx import override
from ....vendor.dataclassesx import dataclass
from ..config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ..schema_dsl.models import DemandConfig
from .allowlist_policy import ResolverTrustedMode

if TYPE_CHECKING:
    import pandas as pd

    from ....execution.run_ir import ExecutionRequest
    from ....ob.presets.viz import VizObserverConfig
    from ....planning.plan import ExecutionPlan
    from ....spec.ir import DemandIr


class _UnsetType:
    __slots__: Tuple[str, ...] = ()

    @override
    def __repr__(self) -> str:
        return "UNSET"


UNSET = _UnsetType()
UnsetType = _UnsetType


@dataclass(frozen=True)
class RunOverrides:
    """运行期覆盖项.

    `outputs` 为与 `YAML` 顶层 `outputs` 同形的输出覆盖片段:

    - `outputs: list[dict]` (非空)
    - 本变更仅承诺明细输出(`detail`)最小子集: `name` / `container` / `fields`
    - 语义为整体替换(`replace`): 提供则整体替换 `YAML` 的 `outputs`(不做 `deep-merge`)
    """

    outputs: Optional[List[Dict[str, Any]]] = None
    viz_config: Union[Optional["VizObserverConfig"], _UnsetType] = UNSET


@dataclass(frozen=True)
class RunOptions:
    allowed_modules: FrozenSet[str]
    """允许被引用/导入的模块白名单(用于安全解析)."""

    allowed_functions: Optional[FrozenSet[str]] = None
    """可选:允许被引用/导入的函数白名单(用于更细粒度的安全控制)."""

    resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST
    """`Python` 引用 `resolver` 的安全模式.

    - `strict_allowlist`(默认): 禁止 `wildcard`,并要求显式 `allowlist`.
    - `trusted_allow_all_modules`: 仅用于可信输入/内部测试;显式放宽为允许任意模块,并产生强告警.
    """

    components: Optional[List[Union[Observer, IExecutionHook]]] = None
    """可选:要挂载的 `Observer`/`Hook` 组件列表."""

    sink: Optional[ISink] = None
    """可选:显式指定输出端;若为 `None` 则按配置创建."""

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

    key_normalization: KeyNormalizationMode = "raw"
    """可选: `key` 规范化模式(实验性)."""

    overrides: Optional[RunOverrides] = None
    """可选:运行期覆盖项(例如输出与 `viz` 配置覆盖)."""

    init_vars: Optional[Dict[str, object]] = None
    """可选:初始化变量注入(编译期使用,用于解析 `params` 中的 `{$init_var: <name>}` 指令节点)."""

    template_vars: Optional[Mapping[str, object]] = None
    """可选:模板变量注入(编译期使用,用于在 `YAML` 解析前对 `YAML` 文本执行 `LiteJinja2` 预编译)."""

    template_sandbox: str = "safe"
    """模板预编译的 `template_sandbox` 模式.

    - `safe`(默认): 禁止无参 `method call`,并禁止访问以下划线开头属性(含 `__dunder__`).
    - `legacy`: 显式放宽(不安全);仅用于可信输入/内部测试.
    """

    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN
    """当启用 `template_vars` 预编译时,渲染后 `YAML` 文本长度上限(字符数)."""

    allowed_yaml_roots: Optional[Tuple[str, ...]] = None
    """可选:允许读取 `YAML` 文件的根目录集合.

    - 若为 `None`(默认),仅允许读取入口 `YAML` 所在目录树内的文件.
    - 若显式提供,仍会自动包含入口 `YAML` 所在目录;用于“受控跨目录复用”(例如 `imports` 或工作流需求引用上层共享目录).
    """

    workflow_managed_output_ids: Optional[FrozenSet[str]] = None
    """可选: `workflow` 托管的 `output_id` 白名单(用于 `workflow-managed` 的无路径 `CSV` 输出的内存物化)."""

    builtin_callables: Optional[Mapping[str, object]] = None
    """可选:内置可调用对象词表(用于 `^<id>` 引用).

    - 键: `<id>` (不包含前缀 `^`)
    - 值: `callable` 或 `Python` 引用字符串(例如 `pkg.mod:fn`)
    - 该词表作为“显式受控白名单”: `^<id>` 的解析与执行不要求把其目标模块加入 `allowlist`
    """

    public_builtin_callable_ids: Optional[Tuple[str, ...]] = None
    """可选:用户可见的内置 `<id>` 列表(用于错误信息/文档提示;应为保守子集)."""


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
        if sink is None or not hasattr(sink, "get_data"):  # pragma: allow-dynattr optional-interface: sink.get_data
            msg = "to_dataframe() requires an in-memory sink with get_data() (e.g. InMemoryRowSink)"
            raise ValueError(msg)
        try:
            pd = import_module("pandas")
            sink_with_data = cast("Any", sink)  # pragma: allow-cast sink get_data typed narrowing
            return pd.DataFrame(sink_with_data.get_data())  # type: ignore[no-any-return]
        except ImportError as e:
            msg = "pandas is required for to_dataframe()"
            raise ImportError(msg) from e


__all__ = [
    "UNSET",
    "Compilation",
    "ResolverTrustedMode",
    "RunOptions",
    "RunOverrides",
    "RunResult",
    "UnsetType",
]
