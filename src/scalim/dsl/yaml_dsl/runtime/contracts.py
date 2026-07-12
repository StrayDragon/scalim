# pragma: allow-c901-file plan: c70
import os
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, Union, cast

from ....execution.guardrails import GuardrailsPolicy
from ....execution.key_normalization import normalize_key_normalization
from ....execution.loader_retry import LoaderRetryPoliciesSpec
from ....execution.run_ir import ExecutionResult
from ....hooks import IExecutionHook
from ....ob.observer import Observer
from ....typedefs import KeyNormalizationMode, ParallelMode
from ....vendor.compact.importlibx import import_module
from ....vendor.compact.typing_extensionsx import override
from ....vendor.dataclassesx import dataclass
from ....vendor.dataclassesx import field as dataclass_field
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ..book_resource_policy import ResourcesPolicy
from ..init_var_nodes import OptionalPathNode
from ..schema_dsl.models import DemandConfig
from .allowlist_policy import ResolverTrustedMode
from .errors import ALLOWLIST_REQUIRED_MSG, ScalimAllowlistRequiredError

if TYPE_CHECKING:
    import pandas as pd

    from ....execution.run_ir import ExecutionRequest
    from ....ob.presets.viz import VizObserverConfig
    from ....planning.plan import ExecutionPlan
    from ....sinks.rows import InMemoryRows
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
    - 本类型属于稳定的公开契约;推荐从 `scalim.dsl.yaml_dsl` 导入.
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
        output_root: Union[str, "os.PathLike[str]"],
        fields: Sequence[str],
        output_name: str = "detail",
        file_id: str = "detail_csv",
        encoding: str = "utf-8",
        include_header: bool = True,
        header_fields_output_by: str = "field_id",
    ) -> "RunOverrides":
        output_root_str = str(os.fspath(output_root)).strip()
        resources = ResourcesOverride(
            files={str(file_id): FileResourceOverride(kind="csv_file", path=str(output_root_str), encoding=str(encoding))}
        )
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
        output_root: Union[str, "os.PathLike[str]"],
        fields: Sequence[str],
        sheet: str,
        output_name: str = "detail",
        book_id: str = "report",
        allow_formulas: bool = True,
        include_header: bool = True,
        header_fields_output_by: str = "field_id",
    ) -> "RunOverrides":
        output_root_str = str(os.fspath(output_root)).strip()
        defaults = OutputsDefaultsOverride(to=OutputDefaultsToOverride(book=str(book_id)))
        resources = ResourcesOverride(
            books={
                str(book_id): BookResourceOverride(
                    kind="xlsx_file",
                    path=str(output_root_str),
                    allow_formulas=bool(allow_formulas),
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
class BookExportXlsxOverride:
    path: OptionalPathNode = None
    allow_formulas: Optional[bool] = None


@dataclass(frozen=True)
class BookResourceOverride:
    kind: Optional[str] = None
    path: OptionalPathNode = None
    export_xlsx: Optional[BookExportXlsxOverride] = None
    allow_formulas: Optional[bool] = None

    def __post_init__(self) -> None:
        # `write_defaults` / `budget` 已迁出 `RunOverrides.resources`(`Python` `ResourcesPolicy` `SSOT`).
        # 保留旧字段名时的 `fail-fast` 由 `resource_override` 补丁层负责.
        pass


@dataclass(frozen=True)
class FileResourceOverride:
    kind: Optional[str] = None
    path: OptionalPathNode = None
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
    - 仅能通过 `Python/CLI` 的运行入口(`runtime entrypoints`)装配(例如 `scalim.dsl.yaml_dsl.run/compile`).
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
class CaptureNone:
    """默认:不捕获内存行数据."""


@dataclass(frozen=True)
class CaptureRows:
    """捕获本次运行产生的行数据(显式开启)."""


CapturePolicy = Union[CaptureNone, CaptureRows]


def _coerce_iterable_str_frozenset(value: Any, *, field_name: str) -> FrozenSet[str]:
    if value is None:
        msg = "{} must be an iterable of str".format(field_name)
        raise TypeError(msg)
    if isinstance(value, str):
        msg = "{} must be an iterable of str (not a str)".format(field_name)
        raise TypeError(msg)
    try:
        return frozenset(str(item) for item in value)
    except TypeError:
        msg = "{} must be an iterable of str".format(field_name)
        raise TypeError(msg) from None


def _coerce_iterable_str_tuple(value: Any, *, field_name: str) -> Tuple[str, ...]:
    if value is None:
        msg = "{} must be an iterable of str".format(field_name)
        raise TypeError(msg)
    if isinstance(value, str):
        msg = "{} must be an iterable of str (not a str)".format(field_name)
        raise TypeError(msg)
    try:
        return tuple(str(item) for item in value)
    except TypeError:
        msg = "{} must be an iterable of str".format(field_name)
        raise TypeError(msg) from None


@dataclass(frozen=True)
class DemandRunSecurityOptions:
    """`demand` 运行的安全边界选项."""

    allowed_modules: FrozenSet[str]
    """允许被引用/导入的模块白名单(用于安全解析)."""

    allowed_functions: Optional[FrozenSet[str]] = None
    """可选:允许被引用/导入的函数白名单(用于更细粒度的安全控制)."""

    resolver_trusted_mode: ResolverTrustedMode = ResolverTrustedMode.STRICT_ALLOWLIST
    """`Python` 引用 `resolver` 的安全模式."""

    allowed_yaml_roots: Optional[Tuple[str, ...]] = None
    """可选:允许读取 `YAML` 文件的根目录集合."""

    builtin_callables: Optional[Mapping[str, object]] = None
    """可选:内置可调用对象词表(用于 `^<id>` 引用)."""

    public_builtin_callable_ids: Optional[Tuple[str, ...]] = None
    """可选:用户可见的内置 `<id>` 列表(用于错误信息/文档提示;应为保守子集)."""

    def __post_init__(self) -> None:
        allowed_modules = _coerce_iterable_str_frozenset(
            self.allowed_modules,
            field_name="DemandRunSecurityOptions.allowed_modules",
        )
        allowed_functions = (
            None
            if self.allowed_functions is None
            else _coerce_iterable_str_frozenset(
                self.allowed_functions,
                field_name="DemandRunSecurityOptions.allowed_functions",
            )
        )
        object.__setattr__(self, "allowed_modules", allowed_modules)
        object.__setattr__(self, "allowed_functions", allowed_functions)

        if not allowed_modules and not allowed_functions:
            raise ScalimAllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)

        mode = self.resolver_trusted_mode
        # 注意: `ResolverTrustedMode` 是 `str-enum`,因此枚举成员同时也是 `str` 实例.
        # 必须先判断枚举类型本身,避免对已是枚举成员的值再次执行 `ResolverTrustedMode(str(mode))`,
        # 因为 `str(enum_member)` 形如 `ResolverTrustedMode.X` 并不是合法枚举值.
        if isinstance(mode, ResolverTrustedMode):
            pass
        elif isinstance(mode, str):
            object.__setattr__(self, "resolver_trusted_mode", ResolverTrustedMode(str(mode)))
        else:
            msg = "DemandRunSecurityOptions.resolver_trusted_mode must be a ResolverTrustedMode"
            raise TypeError(msg)

        if self.allowed_yaml_roots is not None:
            object.__setattr__(
                self,
                "allowed_yaml_roots",
                _coerce_iterable_str_tuple(
                    self.allowed_yaml_roots,
                    field_name="DemandRunSecurityOptions.allowed_yaml_roots",
                ),
            )

        if self.public_builtin_callable_ids is not None:
            object.__setattr__(
                self,
                "public_builtin_callable_ids",
                _coerce_iterable_str_tuple(
                    self.public_builtin_callable_ids,
                    field_name="DemandRunSecurityOptions.public_builtin_callable_ids",
                ),
            )


@dataclass(frozen=True)
class DemandRunTemplateOptions:
    """`demand` 编译期模板/注入相关选项."""

    template_vars: Optional[Mapping[str, object]] = None
    """可选:模板变量注入(编译期使用,用于在 `YAML` 解析前对 `YAML` 文本执行 `LiteJinja2` 预编译)."""

    template_sandbox: str = "safe"
    """模板预编译的 `template_sandbox` 模式(公开入口仅允许 `safe`)."""

    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN
    """当启用 `template_vars` 预编译时,渲染后 `YAML` 文本长度上限(字符数)."""

    init_vars: Optional[Dict[str, object]] = None
    """可选:初始化变量注入(编译期使用,用于解析 `params` 中的 `{$init_var: <name>}` 指令节点)."""

    def __post_init__(self) -> None:
        sandbox = str(self.template_sandbox or "").strip() or "safe"
        object.__setattr__(self, "template_sandbox", sandbox)

        max_len = self.rendered_yaml_max_len
        if isinstance(max_len, bool) or not isinstance(max_len, int):
            msg = "DemandRunTemplateOptions.rendered_yaml_max_len must be an int"
            raise TypeError(msg)
        if int(max_len) <= 0:
            msg = "DemandRunTemplateOptions.rendered_yaml_max_len must be > 0"
            raise ValueError(msg)
        object.__setattr__(self, "rendered_yaml_max_len", int(max_len))


@dataclass(frozen=True)
class DemandRunRuntimeOptions:
    """`demand` 执行期选项(与执行编排相关)."""

    components: Optional[List[Union[Observer, IExecutionHook]]] = None
    """可选:要挂载的 `Observer`/`Hook` 组件列表(作用于 `demand` 执行层)."""

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
    """可选:`demand` 诊断/治理策略."""

    parallel_mode: ParallelMode = "seq"
    """并行模式(`seq` 或 `adaptive`)."""

    max_workers: int = 0
    """最大并发工作数提示(`0` 表示自动).

    注意:
    - 在 `parallel_mode="adaptive"` 下,显式 `max_workers > 0` 会被 `guardrails` 施加 `hard cap`,
      且当发生裁剪时会发出 `warning`(避免外部输入不受控放大并发).
    """

    key_normalization: KeyNormalizationMode = "raw"
    """可选: `key` 规范化模式(实验性)."""

    def __post_init__(self) -> None:
        parallel_mode = self.parallel_mode
        if parallel_mode not in ("seq", "adaptive"):
            msg = "DemandRunRuntimeOptions.parallel_mode must be 'seq' or 'adaptive'"
            raise ValueError(msg)

        max_workers = self.max_workers
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            msg = "DemandRunRuntimeOptions.max_workers must be an int"
            raise TypeError(msg)
        if int(max_workers) < 0:
            msg = "DemandRunRuntimeOptions.max_workers must be >= 0"
            raise ValueError(msg)
        object.__setattr__(self, "max_workers", int(max_workers))

        object.__setattr__(self, "key_normalization", normalize_key_normalization(self.key_normalization))

        raw = self.batch_size
        if isinstance(raw, UnsetType):
            return
        if raw is None:
            return
        if isinstance(raw, bool) or not isinstance(raw, int):
            msg = "DemandRunRuntimeOptions.batch_size must be an integer >= 1, None, or UNSET"
            raise TypeError(msg)
        if int(raw) < 1:
            msg = "DemandRunRuntimeOptions.batch_size must be >= 1 when provided"
            raise ValueError(msg)


@dataclass(frozen=True)
class DemandRunOutputOptions:
    """`demand` 输出与捕获选项."""

    overrides: Optional[RunOverrides] = None
    """可选:运行期覆盖项(例如输出与 `viz` 配置覆盖)."""

    output_version_id: Optional[str] = None
    """可选:覆盖版本化输出(`D-2`)的 `version_id`."""

    workflow_managed_output_ids: Optional[FrozenSet[str]] = None
    """可选: `workflow` 托管的 `output_id` 白名单."""

    capture: CapturePolicy = dataclass_field(default_factory=CaptureNone)
    """显式捕获策略(默认关闭)."""

    def __post_init__(self) -> None:
        if self.workflow_managed_output_ids is not None:
            object.__setattr__(
                self,
                "workflow_managed_output_ids",
                _coerce_iterable_str_frozenset(
                    self.workflow_managed_output_ids,
                    field_name="DemandRunOutputOptions.workflow_managed_output_ids",
                ),
            )

        capture = self.capture
        if not isinstance(capture, (CaptureNone, CaptureRows)):
            msg = "DemandRunOutputOptions.capture must be CaptureNone or CaptureRows"
            raise TypeError(msg)


@dataclass(frozen=True)
class DemandRunOptions:
    """`demand` 官方运行入口(`compile/run`)的 `options` 契约."""

    security: DemandRunSecurityOptions
    template: DemandRunTemplateOptions = dataclass_field(default_factory=DemandRunTemplateOptions)
    runtime: DemandRunRuntimeOptions = dataclass_field(default_factory=DemandRunRuntimeOptions)
    outputs: DemandRunOutputOptions = dataclass_field(default_factory=DemandRunOutputOptions)
    resources_policy: Optional["ResourcesPolicy"] = None

    def __post_init__(self) -> None:
        if not isinstance(self.security, DemandRunSecurityOptions):
            msg = "DemandRunOptions.security must be a DemandRunSecurityOptions"
            raise TypeError(msg)
        if not isinstance(self.template, DemandRunTemplateOptions):
            msg = "DemandRunOptions.template must be a DemandRunTemplateOptions"
            raise TypeError(msg)
        if not isinstance(self.runtime, DemandRunRuntimeOptions):
            msg = "DemandRunOptions.runtime must be a DemandRunRuntimeOptions"
            raise TypeError(msg)
        if not isinstance(self.outputs, DemandRunOutputOptions):
            msg = "DemandRunOptions.outputs must be a DemandRunOutputOptions"
            raise TypeError(msg)
        if self.resources_policy is not None and not isinstance(self.resources_policy, ResourcesPolicy):
            msg = "DemandRunOptions.resources_policy must be a ResourcesPolicy or None"
            raise TypeError(msg)


@dataclass(frozen=True)
class Compilation:
    config: DemandConfig
    demand_ir: "DemandIr"
    request: "ExecutionRequest"


class DemandRunResult:
    core: ExecutionResult
    config: DemandConfig
    yaml_path: str
    captured_rows: Optional["InMemoryRows"]

    def __init__(
        self,
        core: ExecutionResult,
        *,
        config: DemandConfig,
        yaml_path: str,
        captured_rows: Optional["InMemoryRows"] = None,
    ) -> None:
        self.core = core
        self.config = config
        self.yaml_path = yaml_path
        self.captured_rows = captured_rows

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
        captured_rows = self.captured_rows
        if captured_rows is None:
            msg = "to_dataframe() requires capture enabled: DemandRunOptions(outputs=DemandRunOutputOptions(capture=CaptureRows()))"
            raise ValueError(msg)
        try:
            pd = import_module("pandas")
            return pd.DataFrame(list(captured_rows.iter_row_data()))  # type: ignore[no-any-return]
        except ImportError as e:
            msg = "pandas is required for to_dataframe()"
            raise ImportError(msg) from e


__all__ = (
    "UNSET",
    "CaptureNone",
    "CapturePolicy",
    "CaptureRows",
    "Compilation",
    "DemandDiagnosticsOverride",
    "DemandDiagnosticsPolicy",
    "DemandRunOptions",
    "DemandRunOutputOptions",
    "DemandRunResult",
    "DemandRunRuntimeOptions",
    "DemandRunSecurityOptions",
    "DemandRunTemplateOptions",
    "ResolverTrustedMode",
    "RunOverrides",
    "UnsetType",
)
