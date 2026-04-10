import inspect
from collections.abc import Hashable, Mapping
from typing import Any, Callable, Dict, FrozenSet, Optional, Sequence, Tuple, Union, cast
from typing import Mapping as TypingMapping

from ...typedefs import LoaderResultMap, LoaderResultMapping, SourceSpecIrCacheMode, StaticParams
from ...vendor.compact.typing_extensionsx import TypeGuard, override
from ...vendor.dataclassesx import dataclass, field
from ._relations import FieldRefIr
from .aliases import NormalizedLookupKeySpec
from .binding import BindingIr, LoaderIr
from .callable_refs import CallableRefIr
from .lookup_casts import LookupCastSpecIr


@dataclass(frozen=True)
class KeyIr:
    """
    `Key`(IR): 描述数据源返回映射的键结构
    """

    key: Union[str, Tuple[str, ...]]
    """
    键定义.
    """

    cast: Optional[LookupCastSpecIr] = None
    """
    键归一化转换:用于对齐关联键类型.

    例如:`cast=int` 会将 `str(\"123\")` 转换为 `int(123)`.
    """

    def __post_init__(self) -> None:
        if isinstance(self.key, str):
            key = self.key.strip()
            if key.startswith("(") and key.endswith(")") and "," in key:
                msg = "Composite key must be tuple, got string: {}".format(self.key)
                raise ValueError(msg)

    @override
    def __str__(self) -> str:
        return str(self.key)

    @override
    def __hash__(self) -> int:
        return hash(self.key)


@dataclass(frozen=True)
class NormalizeCallByContext:
    source_id: str
    kind: str
    config_path: str


NormalizeCallByFn = Callable[..., object]

_CALL_BY_CTX_POSITIONAL_ARGC = 2


def _is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, (list, tuple))


def _is_mapping(value: object) -> TypeGuard[TypingMapping[object, object]]:
    return isinstance(value, Mapping)


def _is_hashable_mapping(value: object) -> TypeGuard[TypingMapping[Hashable, object]]:
    return isinstance(value, Mapping)


def _is_str_mapping(value: object) -> TypeGuard[TypingMapping[str, object]]:
    return isinstance(value, Mapping)


@dataclass(frozen=True)
class SourceNormalizeProjectFieldRuleIr:
    name: str
    from_key: bool = False
    extract_expr: str = ""
    extract_segments: Tuple[Union[str, int], ...] = ()


@dataclass(frozen=True)
class SourceNormalizeStepIr:
    kind: str
    on_empty: str = "miss"
    on_missing: str = "error"
    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...] = ()

    def apply_value(self, value: object, *, lookup_key: Hashable, source_id: str, step_index: int) -> object:
        if self.kind == "take_first":
            return _normalize_take_first_value(
                value,
                source_id=source_id,
                lookup_key=lookup_key,
                on_empty=self.on_empty,
                config_label="normalize.map_values.steps[{}].take_first".format(step_index),
            )
        if self.kind == "project_fields":
            return _normalize_project_fields_value(
                value,
                source_id=source_id,
                lookup_key=lookup_key,
                fields=self.fields,
                on_missing=self.on_missing,
                config_label="normalize.map_values.steps[{}].project_fields".format(step_index),
            )
        msg = "Unknown normalize.step.kind '{}' for source '{}' at step {}".format(self.kind, source_id, step_index)
        raise ValueError(msg)


_NORMALIZE_MISS = object()


@dataclass(frozen=True)
class SourceNormalizeIr:
    """数据源 `whole-result` `normalize` 配置(`IR`)."""

    kind: str
    """`normalize` 预置类型."""

    key_field: str = ""
    """用于建立索引的 `row` 字段名."""

    on_conflict: str = "error"
    """`duplicate key` 冲突策略(`error`/`first`/`last`)."""

    on_none: str = "raise"
    """`key_field is None` 策略(`raise`/`skip`;仅 `index_by_key`)."""

    on_empty: str = "miss"
    """空列表策略(`miss`/`null`/`error`)."""

    on_missing: str = "error"
    """缺失路径策略(`error`/`null`)."""

    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...] = ()
    """`project_fields` 的投影规则(按顺序)."""

    steps: Tuple[SourceNormalizeStepIr, ...] = ()
    """用于 `normalize.kind: map_values` 的归一化步骤(按顺序)."""

    call_by_ref: Optional[CallableRefIr] = None
    """可选: `normalize.call_by` 可调用引用描述(纯数据,不包含可调用对象)."""

    def apply(
        self,
        result: object,
        *,
        source_id: str,
        call_by: Optional[object] = None,
    ) -> LoaderResultMapping:
        normalized: LoaderResultMapping
        if self.kind == "index_by_key":
            normalized = _normalize_index_by_key(
                result,
                source_id=source_id,
                key_field=self.key_field,
                on_conflict=self.on_conflict,
                on_none=self.on_none,
            )
        elif self.kind == "take_first":
            normalized = _normalize_take_first(
                result,
                source_id=source_id,
                on_empty=self.on_empty,
            )
        elif self.kind == "project_fields":
            normalized = _normalize_project_fields(
                result,
                source_id=source_id,
                fields=self.fields,
                on_missing=self.on_missing,
            )
        elif self.kind == "map_values":
            normalized = _normalize_map_values(
                result,
                source_id=source_id,
                steps=self.steps,
            )
        else:
            msg = "Unknown normalize.kind '{}' for source '{}'".format(self.kind, source_id)
            raise ValueError(msg)

        if self.call_by_ref is None:
            return normalized
        if call_by is None:
            msg = "Source '{}' normalize.call_by_ref requires runtime resolution before apply()".format(source_id)
            raise ValueError(msg)
        if not callable(call_by):
            msg = "Source '{}' normalize.call_by_ref expects callable runtime binding, got '{}'".format(source_id, type(call_by).__name__)
            raise TypeError(msg)
        return _normalize_call_by(
            normalized,
            source_id=source_id,
            kind=self.kind,
            call_by=call_by,
        )


def _normalize_call_by(
    result: object,
    *,
    source_id: str,
    kind: str,
    call_by: NormalizeCallByFn,
) -> LoaderResultMapping:
    config_path = "sources.{}.normalize.call_by".format(source_id)
    if not _is_mapping(result):
        msg = "Source '{}' normalize.call_by expected Mapping input at '{}', got '{}'".format(source_id, config_path, type(result).__name__)
        raise TypeError(msg)

    result_mapping = result
    ctx = NormalizeCallByContext(source_id=source_id, kind=kind, config_path=config_path)
    try:
        returned = _call_normalize_call_by(call_by, result_mapping, ctx)
    except TypeError as exc:
        msg = "Source '{}' normalize.call_by failed to call function at '{}': {}".format(source_id, config_path, str(exc))
        raise TypeError(msg) from exc

    if not isinstance(returned, Mapping):
        msg = "Source '{}' normalize.call_by must return Mapping at '{}', got '{}'".format(source_id, config_path, type(returned).__name__)
        raise TypeError(msg)
    return cast("LoaderResultMapping", returned)  # pragma: allow-cast normalize.call_by return typed narrowing


def _call_normalize_call_by(fn: NormalizeCallByFn, result: object, ctx: NormalizeCallByContext) -> object:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return _call_normalize_call_by_fallback(fn, result, ctx)

    params = list(sig.parameters.values())
    accepts_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)

    try:
        positional_only = inspect.Parameter.POSITIONAL_ONLY
    except AttributeError:
        positional_only = None  # 兼容 `py<3.8`: `inspect.Parameter` 不支持 `POSITIONAL_ONLY`
    positional_kinds = [inspect.Parameter.POSITIONAL_OR_KEYWORD]
    if positional_only is not None:
        positional_kinds.append(positional_only)
    positional = [p for p in params if p.kind in tuple(positional_kinds)]
    kwonly = [p for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY]
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    accepts_ctx_kwonly = any(p.name == "ctx" for p in kwonly)

    if len(positional) >= _CALL_BY_CTX_POSITIONAL_ARGC:
        return fn(result, ctx)

    if len(positional) >= 1 or accepts_varargs:
        if accepts_ctx_kwonly or accepts_kwargs:
            return fn(result, ctx=ctx)  # type: ignore[call-arg]
        if accepts_varargs:
            return fn(result, ctx)
        if len(positional) == 1:
            return fn(result)

    msg = "normalize.call_by must accept at least 1 positional argument: (result) or (result, ctx)"
    raise TypeError(msg)


_CALL_BY_MISMATCH_TOKENS = (
    "positional argument",
    "keyword-only argument",
    "unexpected keyword argument",
    "multiple values for argument",
    "missing ",
    "takes ",
)


def _call_normalize_call_by_fallback(fn: NormalizeCallByFn, result: object, ctx: NormalizeCallByContext) -> object:
    """
    当 `inspect.signature` 无法获取签名时,按约定尝试调用顺序:

    1) `fn(result, ctx)`(推荐签名)
    2) `fn(result, ctx=ctx)`(`keyword-only` 或 `**kwargs`)
    3) `fn(result)`(不接受 `ctx`)

    仅当 `TypeError` 看起来是“参数绑定失败”时才会继续尝试下一个形态,避免吞掉函数体内抛出的 `TypeError`.
    """

    try:
        return fn(result, ctx)
    except TypeError as exc:
        if not _looks_like_call_by_argument_mismatch(exc):
            raise

    try:
        return fn(result, ctx=ctx)  # type: ignore[call-arg]
    except TypeError as exc:
        if not _looks_like_call_by_argument_mismatch(exc):
            raise

    return fn(result)


def _looks_like_call_by_argument_mismatch(exc: TypeError) -> bool:
    tb = exc.__traceback__
    if tb is not None and tb.tb_next is not None:
        return False
    msg = str(exc)
    return any(token in msg for token in _CALL_BY_MISMATCH_TOKENS)


class _IndexByKeyNormalizedMapping(dict):  # pyright: ignore[reportMissingTypeArgument]
    skipped_none_rows: int


def _normalize_index_by_key(
    result: object,
    *,
    source_id: str,
    key_field: str,
    on_conflict: str,
    on_none: str,
) -> LoaderResultMapping:
    # 若 `loader` 已返回 `mapping`,则直接透传.
    if isinstance(result, Mapping):
        return cast("LoaderResultMapping", result)  # pragma: allow-cast normalize.index_by_key mapping passthrough

    if on_none not in {"raise", "skip"}:
        msg = "Source '{}' normalize.index_by_key has invalid on_none '{}' (config: sources.{}.normalize.on_none)".format(
            source_id,
            on_none,
            source_id,
        )
        raise ValueError(msg)

    if not _is_sequence(result):
        msg = "Source '{}' normalize.index_by_key expected loader result list[row], got '{}'".format(source_id, type(result).__name__)
        raise TypeError(msg)

    indexed: LoaderResultMap = {}
    indexed_stats: Optional[_IndexByKeyNormalizedMapping] = None
    skipped_none_rows = 0
    if on_none == "skip":
        indexed_stats = _IndexByKeyNormalizedMapping()
        indexed = cast("LoaderResultMap", cast("object", indexed_stats))  # pragma: allow-cast dict subclass as LoaderResultMap
    for idx, item in enumerate(result):
        row = _normalize_index_by_key_require_row(item, source_id=source_id, idx=idx)
        key = _normalize_index_by_key_extract_key(row, source_id=source_id, key_field=key_field, idx=idx, on_none=on_none)
        if key is None:
            skipped_none_rows += 1
            continue
        _normalize_index_by_key_insert(indexed, key=key, row=row, source_id=source_id, on_conflict=on_conflict, idx=idx)

    if indexed_stats is not None:
        indexed_stats.skipped_none_rows = int(skipped_none_rows)
    return indexed


def _normalize_take_first(
    result: object,
    *,
    source_id: str,
    on_empty: str,
) -> LoaderResultMapping:
    if isinstance(result, (list, tuple)):
        msg = (
            "Source '{}' normalize.take_first does not support loader result list[row]. "
            "Use normalize.kind=index_by_key with on_conflict to handle duplicate keys."
        ).format(source_id)
        raise TypeError(msg)

    if not _is_hashable_mapping(result):
        msg = "Source '{}' normalize.take_first expected loader result mapping[key -> list[row]], got '{}'".format(
            source_id, type(result).__name__
        )
        raise TypeError(msg)

    out: LoaderResultMap = {}
    for lookup_key, candidates_obj in result.items():
        normalized = _normalize_take_first_value(
            candidates_obj,
            source_id=source_id,
            lookup_key=lookup_key,
            on_empty=on_empty,
            config_label="normalize.take_first",
        )
        if normalized is _NORMALIZE_MISS:
            continue
        out[lookup_key] = normalized
    return out


def _normalize_take_first_value(
    candidates_obj: object,
    *,
    source_id: str,
    lookup_key: Hashable,
    on_empty: str,
    config_label: str,
) -> object:
    if not _is_sequence(candidates_obj):
        msg = "Source '{}' {} expected list[row] for key '{}', got '{}'".format(
            source_id, config_label, lookup_key, type(candidates_obj).__name__
        )
        raise TypeError(msg)

    candidates = candidates_obj
    if not candidates:
        if on_empty == "miss":
            return _NORMALIZE_MISS
        if on_empty == "null":
            return None
        if on_empty != "error":
            msg = "Source '{}' {} has invalid on_empty '{}'".format(source_id, config_label, on_empty)
            raise ValueError(msg)
        msg = "Source '{}' {} got empty candidates list for key '{}'".format(source_id, config_label, lookup_key)
        raise ValueError(msg)

    first = candidates[0]
    if not _is_mapping(first):
        msg = "Source '{}' {} expected row to be a Mapping for key '{}', got '{}'".format(
            source_id, config_label, lookup_key, type(first).__name__
        )
        raise TypeError(msg)
    return first


def _normalize_project_fields(
    result: object,
    *,
    source_id: str,
    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...],
    on_missing: str,
) -> LoaderResultMapping:
    if not _is_hashable_mapping(result):
        msg = "Source '{}' normalize.project_fields expected loader result mapping[key -> row], got '{}'".format(
            source_id, type(result).__name__
        )
        raise TypeError(msg)

    out: LoaderResultMap = {}
    for lookup_key, row_obj in result.items():
        projected = _normalize_project_fields_value(
            row_obj,
            source_id=source_id,
            lookup_key=lookup_key,
            fields=fields,
            on_missing=on_missing,
            config_label="normalize.project_fields",
        )
        out[lookup_key] = projected
    return out


def _normalize_project_fields_value(
    row_obj: object,
    *,
    source_id: str,
    lookup_key: Hashable,
    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...],
    on_missing: str,
    config_label: str,
) -> object:
    if not _is_mapping(row_obj):
        msg = "Source '{}' {} expected row to be a Mapping for key '{}', got '{}'".format(
            source_id, config_label, lookup_key, type(row_obj).__name__
        )
        raise TypeError(msg)

    row = row_obj
    projected: Dict[str, object] = {}
    for rule in fields:
        if rule.from_key:
            projected[rule.name] = lookup_key
            continue

        ok, value = _extract_segments_with_presence(row, rule.extract_segments)
        if ok:
            projected[rule.name] = value
            continue

        if on_missing == "null":
            projected[rule.name] = None
            continue
        if on_missing != "error":
            msg = "Source '{}' {} has invalid on_missing '{}'".format(source_id, config_label, on_missing)
            raise ValueError(msg)
        msg = "Source '{}' {} missing extract '{}' for field '{}' (key '{}')".format(
            source_id,
            config_label,
            rule.extract_expr,
            rule.name,
            lookup_key,
        )
        raise KeyError(msg)

    return projected


def _normalize_map_values(
    result: object,
    *,
    source_id: str,
    steps: Tuple[SourceNormalizeStepIr, ...],
) -> LoaderResultMapping:
    if not _is_hashable_mapping(result):
        msg = "Source '{}' normalize.map_values expected loader result Mapping, got '{}'".format(source_id, type(result).__name__)
        raise TypeError(msg)

    out: LoaderResultMap = {}
    for lookup_key, value in result.items():
        current: object = value
        skip = False
        for idx, step in enumerate(steps):
            current = step.apply_value(current, lookup_key=lookup_key, source_id=source_id, step_index=idx)
            if current is _NORMALIZE_MISS:
                skip = True
                break
        if skip:
            continue
        out[lookup_key] = current
    return out


def _extract_segments_with_presence(
    data: object,
    segments: Tuple[Union[str, int], ...],
) -> Tuple[bool, object]:
    current: object = data
    for segment in segments:
        if current is None:
            return False, None
        ok, current = _extract_segment_with_presence(current, segment)
        if not ok:
            return False, None
    return True, current


def _extract_segment_with_presence(
    data: object,
    segment: Union[str, int],
) -> Tuple[bool, object]:
    if _is_mapping(data):
        mapping = data
        if segment in mapping:
            return True, mapping[segment]
        return False, None

    if isinstance(segment, str):
        try:
            return True, object.__getattribute__(data, segment)  # type: ignore[call-arg]
        except AttributeError:
            pass

    if isinstance(segment, int) and isinstance(data, (list, tuple)):
        return False, None

    try:
        indexable: Any = data
        return True, indexable[segment]
    except (LookupError, TypeError):
        return False, None


def _normalize_index_by_key_require_row(item: object, *, source_id: str, idx: int) -> "Mapping[str, object]":
    if not _is_str_mapping(item):
        msg = "Source '{}' normalize.index_by_key expected list[row] where row is a Mapping, got '{}' at index {}".format(
            source_id,
            type(item).__name__,
            idx,
        )
        raise TypeError(msg)
    return item


def _normalize_index_by_key_extract_key(
    row: "Mapping[str, object]",
    *,
    source_id: str,
    key_field: str,
    idx: int,
    on_none: str,
) -> Optional[Hashable]:
    config_key_field = "sources.{}.normalize.key_field".format(source_id)
    config_on_none = "sources.{}.normalize.on_none".format(source_id)
    if key_field not in row:
        msg = "Source '{}' normalize.index_by_key missing key_field '{}' at row index {} (config: {})".format(
            source_id,
            key_field,
            idx,
            config_key_field,
        )
        raise KeyError(msg)
    key = row.get(key_field)
    if key is None:
        if on_none == "skip":
            return None
        msg = (
            "Source '{}' normalize.index_by_key key_field '{}' is None at row index {} (config: {}). To skip None keys, set {}: skip"
        ).format(source_id, key_field, idx, config_key_field, config_on_none)
        raise ValueError(msg)
    if not isinstance(key, Hashable):
        msg = "Source '{}' normalize.index_by_key key_field '{}' must be hashable, got '{}' at row index {} (config: {})".format(
            source_id,
            key_field,
            type(key).__name__,
            idx,
            config_key_field,
        )
        raise TypeError(msg)
    return key


def _normalize_index_by_key_insert(
    indexed: LoaderResultMap,
    *,
    key: Hashable,
    row: "Mapping[str, object]",
    source_id: str,
    on_conflict: str,
    idx: int,
) -> None:
    if key not in indexed:
        indexed[key] = row
        return
    if on_conflict == "first":
        return
    if on_conflict == "last":
        indexed[key] = row
        return
    if on_conflict != "error":
        config_on_conflict = "sources.{}.normalize.on_conflict".format(source_id)
        msg = "Source '{}' normalize.index_by_key has invalid on_conflict '{}' (config: {})".format(
            source_id, on_conflict, config_on_conflict
        )
        raise ValueError(msg)
    msg = "Source '{}' normalize.index_by_key duplicate key '{}' at row index {}".format(source_id, key, idx)
    raise ValueError(msg)


@dataclass(frozen=True)
class SourceIr:
    """
    数据源(IR): 定义一个数据源的完整信息,包括主键、外键、加载器和绑定
    """

    source_id: str
    """
    数据源唯一标识
    """

    key: KeyIr
    """
    键信息.
    """

    loader_spec: LoaderIr
    """
    加载器信息
    """

    fk_fields: FrozenSet[str] = field(default_factory=frozenset)
    """
    外键字段名集合
    """

    cache_mode: SourceSpecIrCacheMode = SourceSpecIrCacheMode.NONE
    """
    缓存模式
    """

    lookup_chunk_size: Optional[int] = None
    """
    在 `keys` 模式下,引用加载的 `lookup_keys` 分片大小;`None`/`0` 表示不分片.
    """

    bindings: Dict[NormalizedLookupKeySpec, BindingIr] = field(default_factory=dict, compare=False, hash=False)
    """
    参数绑定映射(`key_field` -> `BindingIr`).
    """

    bind: Optional[BindingIr] = None
    """
    默认绑定(当无 `key_field` 匹配时使用).
    """

    normalize: Optional[SourceNormalizeIr] = None
    """
    数据源 `whole-result` `normalize` 配置(可选).
    """

    def get_binding(self, key_field: NormalizedLookupKeySpec) -> Optional[BindingIr]:
        """获取指定键字段的绑定.

        参数:
            `key_field`: 键字段名(字符串或字符串元组,用于复合主键)
        """
        binding = self.loader_spec.get_binding(key_field)
        if binding is None:
            return self.bind
        return binding

    def is_preload_forever(self) -> bool:
        return self.cache_mode == SourceSpecIrCacheMode.PRELOAD_FOREVER

    def __getitem__(self, field_name: str) -> FieldRefIr:
        """支持 `Source[\"field\"]` 语法创建字段引用.

        参数:
            `field_name`: 字段名

        示例:
            - `orders_source[\"customer_id\"].join(customers_source[\"customer_id\"])`

        """
        return FieldRefIr(source=self, field_name=field_name)

    @override
    def __hash__(self) -> int:
        return hash(self.source_id)


@dataclass(frozen=True)
class MainSourceIr:
    """
    主数据源(IR): 以行流方式提供数据,由框架分配 `row_id` 进行索引
    """

    source_id: str
    """
    数据源唯一标识
    """

    loader_ref: CallableRefIr
    """主数据源加载器引用描述(纯数据,不包含可调用对象)."""

    params: StaticParams = field(default_factory=dict)
    """
    加载器静态参数(直接透传给加载器函数).
    """

    order_by: Tuple["OrderByKeyIr", ...] = field(default_factory=tuple)
    """
    批次内排序键(字段 + 方向);仅影响写入顺序,不改变 `row_id` 分配.
    """

    row_id_key: str = "row_id"
    """
    内部行标识字段名 (框架维护)
    """

    def __getitem__(self, field_name: str) -> FieldRefIr:
        """支持 `MainSource[\"field\"]` 语法创建字段引用."""
        return FieldRefIr(source=self, field_name=field_name)

    @override
    def __hash__(self) -> int:
        return hash(self.source_id)


@dataclass(frozen=True)
class OrderByKeyIr:
    """
    主数据源批次排序键(IR)
    """

    field_key: str
    """
    排序字段键(主数据源字段).
    """

    direction: str = "asc"
    """
    排序方向:`asc`/`desc`.
    """


SourceRefIr = Union["SourceIr", "MainSourceIr"]

__all__ = ()
