from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, Union, cast

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
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ..schema_dsl.models import DemandConfig
from .allowlist_policy import ResolverTrustedMode

if TYPE_CHECKING:
    import os

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

    说明:
    - 本类型属于稳定的公开契约;推荐从 `scalim.dsl.by_yaml` 导入.
    - 本变更移除旧的 YAML 同形 `dict/list[dict]` `overrides` 输入;改为强类型 `dataclasses`.

    语义:
    - `outputs`: 非空序列时表示整体替换(最高优先级),覆盖 YAML `outputs`.
    - `resources`: 仅 `IO` 层覆盖,语义为叠加/深合并(`overlay`/`deep-merge`),覆盖 YAML `resources.*`.
    """

    outputs: Optional[Sequence["OutputOverride"]] = None
    resources: Optional["ResourcesOverride"] = None
    outputs_defaults: Optional["OutputsDefaultsOverride"] = None
    output_extras: Optional["OutputExtrasOverride"] = None
    viz_config: Union[Optional["VizObserverConfig"], _UnsetType] = UNSET

    def __post_init__(self) -> None:  # noqa: C901, PLR0912
        if self.outputs is not None:
            outputs = tuple(self.outputs)
            if not outputs:
                msg = "RunOverrides.outputs cannot be empty (pass None to use YAML outputs)"
                raise ValueError(msg)
            if any(isinstance(item, dict) for item in outputs):
                msg = (
                    "Legacy YAML-shaped overrides are no longer supported: RunOverrides.outputs=list[dict]. "
                    "Migrate to typed dataclasses: RunOverrides(outputs=(OutputOverride(...),), resources=ResourcesOverride(...))."
                )
                raise TypeError(msg)
            if any(not isinstance(item, OutputOverride) for item in outputs):
                msg = "RunOverrides.outputs must be a sequence of OutputOverride"
                raise TypeError(msg)
            object.__setattr__(self, "outputs", outputs)

        if self.resources is not None:
            if isinstance(self.resources, dict):
                msg = (
                    "Legacy YAML-shaped overrides are no longer supported: RunOverrides.resources=dict. "
                    "Migrate to typed dataclasses: RunOverrides(resources=ResourcesOverride(...))."
                )
                raise TypeError(msg)
            if not isinstance(self.resources, ResourcesOverride):
                msg = "RunOverrides.resources must be a ResourcesOverride"
                raise TypeError(msg)

        if self.outputs_defaults is not None:
            if isinstance(self.outputs_defaults, dict):
                msg = (
                    "Legacy YAML-shaped overrides are no longer supported: RunOverrides.outputs_defaults=dict. "
                    "Migrate to typed dataclasses: RunOverrides(outputs_defaults=OutputsDefaultsOverride("
                    "to=OutputDefaultsToOverride(book=...)))."
                )
                raise TypeError(msg)
            if not isinstance(self.outputs_defaults, OutputsDefaultsOverride):
                msg = "RunOverrides.outputs_defaults must be an OutputsDefaultsOverride"
                raise TypeError(msg)

        if self.output_extras is not None:
            if isinstance(self.output_extras, dict):
                msg = (
                    "Legacy YAML-shaped overrides are no longer supported: RunOverrides.output_extras=dict. "
                    "Migrate to typed dataclasses: RunOverrides(output_extras=OutputExtrasOverride(meta=True, audit=True))."
                )
                raise TypeError(msg)
            if not isinstance(self.output_extras, OutputExtrasOverride):
                msg = "RunOverrides.output_extras must be an OutputExtrasOverride"
                raise TypeError(msg)

    @classmethod
    def csv_file(
        cls,
        *,
        output_path: Union[str, "os.PathLike[str]"],
        fields: Sequence[str],
        output_name: str = "detail",
        file_id: str = "detail_csv",
        encoding: str = "utf-8",
        include_header: bool = True,
        header_fields_output_by: str = "field_id",
    ) -> "RunOverrides":
        resources = ResourcesOverride(files={str(file_id): FileResourceOverride(kind="csv_file", path=output_path, encoding=str(encoding))})
        output = OutputOverride(
            name=str(output_name),
            fields=tuple(str(x) for x in fields),
            to=OutputToOverride(file=str(file_id)),
            write=OutputWriteOverride(include_header=bool(include_header), header_fields_output_by=str(header_fields_output_by)),
        )
        return cls(outputs=(output,), resources=resources)

    @classmethod
    def xlsx_file_single_sheet(
        cls,
        *,
        output_path: Union[str, "os.PathLike[str]"],
        fields: Sequence[str],
        sheet: str,
        output_name: str = "detail",
        book_id: str = "report",
        allow_formulas: bool = False,
        write_lock: bool = False,
        include_header: bool = True,
        header_fields_output_by: str = "field_id",
    ) -> "RunOverrides":
        defaults = OutputsDefaultsOverride(to=OutputDefaultsToOverride(book=str(book_id)))
        resources = ResourcesOverride(
            books={
                str(book_id): BookResourceOverride(
                    kind="xlsx_file",
                    path=output_path,
                    allow_formulas=bool(allow_formulas),
                    write_lock=bool(write_lock),
                    write_defaults=BookWriteDefaultsOverride(mode="sheet"),
                )
            }
        )
        output = OutputOverride(
            name=str(output_name),
            fields=tuple(str(x) for x in fields),
            to=OutputToOverride(sheet=str(sheet)),
            write=OutputWriteOverride(
                include_header=bool(include_header),
                header_fields_output_by=str(header_fields_output_by),
            ),
        )
        return cls(outputs=(output,), resources=resources, outputs_defaults=defaults)


@dataclass(frozen=True)
class OutputToOverride:
    file: Optional[str] = None
    book: Optional[str] = None
    sheet: Optional[str] = None

    def __post_init__(self) -> None:
        file_id = str(self.file).strip() if self.file is not None else None
        book_id = str(self.book).strip() if self.book is not None else None
        sheet = str(self.sheet).strip() if self.sheet is not None else None
        object.__setattr__(self, "file", file_id or None)
        object.__setattr__(self, "book", book_id or None)
        object.__setattr__(self, "sheet", sheet or None)


@dataclass(frozen=True)
class OutputWriteOverride:
    include_header: Optional[bool] = None
    header_fields_output_by: Optional[str] = None

    def __post_init__(self) -> None:
        header_by = str(self.header_fields_output_by).strip() if self.header_fields_output_by is not None else None
        object.__setattr__(self, "header_fields_output_by", header_by or None)


@dataclass(frozen=True)
class OutputExtraSheetOverride:
    path: Optional[Union[str, "os.PathLike[str]"]] = None
    sheet: Optional[str] = None
    allow_formulas: Optional[bool] = None
    write_lock: Optional[bool] = None

    def __post_init__(self) -> None:
        sheet = str(self.sheet).strip() if self.sheet is not None else None
        object.__setattr__(self, "sheet", sheet or None)


@dataclass(frozen=True)
class OutputExtrasOverride:
    """运行期输出附加工作表(例如 `meta`/`audit`).

    注意:
    - 该能力从 `YAML` 主线迁出,仅能通过运行入口参数(例如 `RunOverrides.output_extras`)配置.
    """

    meta: Optional[Union[bool, OutputExtraSheetOverride]] = None
    audit: Optional[Union[bool, OutputExtraSheetOverride]] = None

    def __post_init__(self) -> None:
        def _validate(item: object, *, key: str) -> None:
            if item is None:
                return
            if item is True or item is False:
                return
            if isinstance(item, OutputExtraSheetOverride):
                return
            msg = "{} must be a boolean or an OutputExtraSheetOverride".format(key)
            raise TypeError(msg)

        _validate(self.meta, key="meta")
        _validate(self.audit, key="audit")


@dataclass(frozen=True)
class OutputOverride:
    name: str
    fields: Tuple[str, ...]
    to: OutputToOverride
    write: Optional[OutputWriteOverride] = None

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        object.__setattr__(self, "name", name)

        fields_raw_any: Any = self.fields  # pragma: allow-any typed contract input normalization boundary
        if not isinstance(fields_raw_any, tuple):
            fields_raw_any = tuple(fields_raw_any)
        fields_raw = cast("Tuple[object, ...]", fields_raw_any)  # pragma: allow-cast contract input normalization boundary
        normalized: List[str] = []
        for item in fields_raw:
            normalized.append(str(item).strip())
        object.__setattr__(self, "fields", tuple(normalized))


@dataclass(frozen=True)
class BookWriteDefaultsOverride:
    mode: Optional[str] = None
    align_by: Optional[str] = None
    header_policy: Optional[str] = None
    on_mismatch: Optional[str] = None
    on_conflict: Optional[str] = None


@dataclass(frozen=True)
class BookBudgetOverride:
    max_sheets: Optional[int] = None
    max_total_cells: Optional[int] = None


@dataclass(frozen=True)
class BookExportXlsxOverride:
    path: Optional[Union[str, "os.PathLike[str]"]] = None
    write_lock: Optional[bool] = None
    allow_formulas: Optional[bool] = None


@dataclass(frozen=True)
class BookResourceOverride:
    kind: Optional[str] = None
    path: Optional[Union[str, "os.PathLike[str]"]] = None
    budget: Optional[BookBudgetOverride] = None
    export_xlsx: Optional[BookExportXlsxOverride] = None
    allow_formulas: Optional[bool] = None
    write_lock: Optional[bool] = None
    write_defaults: Optional[BookWriteDefaultsOverride] = None


@dataclass(frozen=True)
class FileResourceOverride:
    kind: Optional[str] = None
    path: Optional[Union[str, "os.PathLike[str]"]] = None
    encoding: Optional[str] = None


@dataclass(frozen=True)
class ResourcesOverride:
    books: Optional[Mapping[str, BookResourceOverride]] = None
    files: Optional[Mapping[str, FileResourceOverride]] = None

    def __post_init__(self) -> None:
        books = dict(self.books or {})
        files = dict(self.files or {})
        object.__setattr__(self, "books", books or None)
        object.__setattr__(self, "files", files or None)


@dataclass(frozen=True)
class OutputDefaultsToOverride:
    book: Optional[str] = None

    def __post_init__(self) -> None:
        book_id = str(self.book).strip() if self.book is not None else None
        object.__setattr__(self, "book", book_id or None)


@dataclass(frozen=True)
class OutputsDefaultsOverride:
    to: OutputDefaultsToOverride

    def __post_init__(self) -> None:
        if not isinstance(self.to, OutputDefaultsToOverride):
            msg = "OutputsDefaultsOverride.to must be an OutputDefaultsToOverride"
            raise TypeError(msg)


@dataclass(frozen=True)
class DemandDiagnosticsPolicy:
    """`demand` 诊断/治理策略(运行期注入).

    说明:
    - 该策略从 `demand` YAML 主线迁出,避免被复制粘贴到业务 YAML 造成治理失控.
    - 仅能通过 `Python/CLI` 的运行入口(`runtime entrypoints`)装配(例如 `scalim.dsl.by_yaml.run/compile`).
    """

    include_full_error_message: bool = False
    validate_unique_field_names: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.include_full_error_message, bool):
            msg = "DemandDiagnosticsPolicy.include_full_error_message must be a boolean"
            raise TypeError(msg)
        if not isinstance(self.validate_unique_field_names, bool):
            msg = "DemandDiagnosticsPolicy.validate_unique_field_names must be a boolean"
            raise TypeError(msg)


@dataclass(frozen=True)
class DemandDiagnosticsOverride:
    """`DemandDiagnosticsPolicy` 的字段级补丁(用于 `workflow` 的 `per-run` 覆盖).

    三态约定:
    - `UNSET`: 继承/不覆盖
    - `bool`: 显式覆盖
    """

    include_full_error_message: Union[bool, UnsetType] = UNSET
    validate_unique_field_names: Union[bool, UnsetType] = UNSET

    def __post_init__(self) -> None:
        include_full = self.include_full_error_message
        if not isinstance(include_full, UnsetType) and not isinstance(include_full, bool):
            msg = "DemandDiagnosticsOverride.include_full_error_message must be a boolean or UNSET"
            raise TypeError(msg)

        validate_unique = self.validate_unique_field_names
        if not isinstance(validate_unique, UnsetType) and not isinstance(validate_unique, bool):
            msg = "DemandDiagnosticsOverride.validate_unique_field_names must be a boolean or UNSET"
            raise TypeError(msg)


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

    batch_size: Union[Optional[int], UnsetType] = UNSET
    """可选:覆盖批大小.

    - `UNSET`(默认): 不覆盖,使用配置/默认值
    - `None`: 显式关闭分批处理
    - `int`: 显式覆盖为批大小(>= 1)
    """

    demand_failure_policy: Optional[str] = None
    """可选:覆盖 `demand` 多输出失败策略(`None` 表示不覆盖)."""

    demand_diagnostics: Optional["DemandDiagnosticsPolicy"] = None
    """可选:`demand` 诊断/治理策略(从 YAML 主线迁出,通过运行入口参数装配)."""

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


__all__ = (
    "UNSET",
    "Compilation",
    "DemandDiagnosticsOverride",
    "DemandDiagnosticsPolicy",
    "ResolverTrustedMode",
    "RunOptions",
    "RunOverrides",
    "RunResult",
    "UnsetType",
)
