# pragma: allow-cast-file normalize boundary typed narrowing
"""数据源 `normalize` 运行时变换函数.

提供 `SourceNormalizeIr.apply` 和 `SourceNormalizeStepIr.apply_value`
所依赖的变换逻辑,包括 `index_by_key`、`take_first`、`project_fields`、
`map_values` 以及 `call_by` 五种归一化策略的具体实现.
"""

import inspect
from collections.abc import Hashable, Mapping
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, Union, cast
from typing import Mapping as TypingMapping

from ...typedefs import LoaderResultMap, LoaderResultMapping, RowData, RuntimeValue
from ...vendor.compact.typing_extensionsx import Literal, TypeGuard
from ...vendor.dataclassesx import dataclass

__all__ = ()

NormalizeKind = Literal["index_by_key", "take_first", "project_fields", "map_values"]
NormalizeStepKind = Literal["take_first", "project_fields"]

NormalizeOnConflict = Literal["error", "first", "last"]
NormalizeOnNone = Literal["raise", "skip"]
NormalizeOnEmpty = Literal["miss", "null", "error"]
NormalizeOnMissing = Literal["error", "null"]


# ---------------------------------------------------------------------------
# `normalize` IR 数据类
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceNormalizeProjectFieldRuleIr:
    """`project_fields` 步骤中的单个字段投影规则."""

    name: str
    from_key: bool = False
    extract_expr: str = ""
    extract_segments: Tuple[Union[str, int], ...] = ()


@dataclass(frozen=True)
class SourceNormalizeStepIr:
    """`normalize.map_values` 分支中的单个归一化步骤."""

    kind: NormalizeStepKind
    on_empty: NormalizeOnEmpty = "miss"
    on_missing: NormalizeOnMissing = "error"
    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...] = ()

    def apply_value(self, value: RuntimeValue, *, lookup_key: Hashable, source_id: str, step_index: int) -> RuntimeValue:
        if self.kind == "take_first":
            return normalize_take_first_value(
                value,
                source_id=source_id,
                lookup_key=lookup_key,
                on_empty=self.on_empty,
                config_label="normalize.map_values.steps[{}].take_first".format(step_index),
            )
        if self.kind == "project_fields":
            return normalize_project_fields_value(
                value,
                source_id=source_id,
                lookup_key=lookup_key,
                fields=self.fields,
                on_missing=self.on_missing,
                config_label="normalize.map_values.steps[{}].project_fields".format(step_index),
            )
        msg = "Unknown normalize.step.kind '{}' for source '{}' at step {}".format(self.kind, source_id, step_index)
        raise ValueError(msg)


NormalizeCallByFn = Callable[..., RuntimeValue]

NORMALIZE_MISS = object()
"""`normalize` 步骤返回此哨兵表示"跳过该条目"."""


# ---------------------------------------------------------------------------
# `NormalizeCallByContext`
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizeCallByContext:
    source_id: str
    kind: NormalizeKind
    config_path: str


# ---------------------------------------------------------------------------
# `TypeGuard` 辅助
# ---------------------------------------------------------------------------

_CALL_BY_CTX_POSITIONAL_ARGC = 2


def _is_sequence(value: RuntimeValue) -> TypeGuard[Sequence[RuntimeValue]]:
    return isinstance(value, (list, tuple))


def _is_mapping(value: RuntimeValue) -> TypeGuard[TypingMapping[RuntimeValue, RuntimeValue]]:
    return isinstance(value, Mapping)


def _is_hashable_mapping(value: RuntimeValue) -> TypeGuard[TypingMapping[Hashable, RuntimeValue]]:
    return isinstance(value, Mapping)


def _is_str_mapping(value: RuntimeValue) -> TypeGuard[RowData]:
    return isinstance(value, Mapping)


# ---------------------------------------------------------------------------
# `call_by`
# ---------------------------------------------------------------------------


def normalize_call_by(
    result: RuntimeValue,
    *,
    source_id: str,
    kind: NormalizeKind,
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


def _call_normalize_call_by(fn: NormalizeCallByFn, result: RuntimeValue, ctx: NormalizeCallByContext) -> RuntimeValue:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return _call_normalize_call_by_fallback(fn, result, ctx)

    params = list(sig.parameters.values())
    accepts_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)

    try:
        positional_only = inspect.Parameter.POSITIONAL_ONLY
    except AttributeError:
        positional_only = None
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


def _call_normalize_call_by_fallback(fn: NormalizeCallByFn, result: RuntimeValue, ctx: NormalizeCallByContext) -> RuntimeValue:
    """
    当 `inspect.signature` 无法获取签名时,按约定尝试调用顺序:

    1) `fn(result, ctx)`(推荐签名)
    2) `fn(result, ctx=ctx)`(`keyword-only` 或 `**kwargs`)
    3) `fn(result)`(不接受 `ctx`)

    仅当 `TypeError` 看起来是"参数绑定失败"时才会继续尝试下一个形态,避免吞掉函数体内抛出的 `TypeError`.
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


# ---------------------------------------------------------------------------
# `index_by_key`
# ---------------------------------------------------------------------------


class IndexByKeyNormalizedMapping(dict):  # pyright: ignore[reportMissingTypeArgument]
    skipped_none_rows: int


def normalize_index_by_key(
    result: RuntimeValue,
    *,
    source_id: str,
    key_field: str,
    on_conflict: str,
    on_none: str,
) -> LoaderResultMapping:
    if isinstance(result, Mapping):
        return cast("LoaderResultMapping", result)  # pragma: allow-cast normalize.index_by_key mapping passthrough

    if on_none not in {"raise", "skip"}:
        msg = "Source '{}' normalize.index_by_key has invalid on_none '{}' (config: sources.{}.normalize.index_by_key.on_none)".format(
            source_id,
            on_none,
            source_id,
        )
        raise ValueError(msg)

    if not _is_sequence(result):
        msg = "Source '{}' normalize.index_by_key expected loader result list[row], got '{}'".format(source_id, type(result).__name__)
        raise TypeError(msg)

    indexed: LoaderResultMap = {}
    indexed_stats: Optional[IndexByKeyNormalizedMapping] = None
    skipped_none_rows = 0
    if on_none == "skip":
        stats = IndexByKeyNormalizedMapping()
        indexed_stats = stats
        indexed = cast("LoaderResultMap", stats)  # pragma: allow-cast dict subclass as LoaderResultMap
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


def _normalize_index_by_key_require_row(item: RuntimeValue, *, source_id: str, idx: int) -> RowData:
    if not _is_str_mapping(item):
        msg = "Source '{}' normalize.index_by_key expected list[row] where row is a Mapping, got '{}' at index {}".format(
            source_id,
            type(item).__name__,
            idx,
        )
        raise TypeError(msg)
    return item


def _normalize_index_by_key_extract_key(
    row: RowData,
    *,
    source_id: str,
    key_field: str,
    idx: int,
    on_none: str,
) -> Optional[Hashable]:
    config_key_field = "sources.{}.normalize.index_by_key.key_field".format(source_id)
    config_on_none = "sources.{}.normalize.index_by_key.on_none".format(source_id)
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
    row: RowData,
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
        config_on_conflict = "sources.{}.normalize.index_by_key.on_conflict".format(source_id)
        msg = "Source '{}' normalize.index_by_key has invalid on_conflict '{}' (config: {})".format(
            source_id, on_conflict, config_on_conflict
        )
        raise ValueError(msg)
    msg = "Source '{}' normalize.index_by_key duplicate key '{}' at row index {}".format(source_id, key, idx)
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# `take_first`
# ---------------------------------------------------------------------------


def normalize_take_first(
    result: RuntimeValue,
    *,
    source_id: str,
    on_empty: str,
) -> LoaderResultMapping:
    if isinstance(result, (list, tuple)):
        msg = (
            "Source '{}' normalize.take_first does not support loader result list[row]. "
            "Use normalize.index_by_key with on_conflict to handle duplicate keys."
        ).format(source_id)
        raise TypeError(msg)

    if not _is_hashable_mapping(result):
        msg = "Source '{}' normalize.take_first expected loader result mapping[key -> list[row]], got '{}'".format(
            source_id, type(result).__name__
        )
        raise TypeError(msg)

    out: LoaderResultMap = {}
    for lookup_key, candidates_obj in result.items():
        normalized = normalize_take_first_value(
            candidates_obj,
            source_id=source_id,
            lookup_key=lookup_key,
            on_empty=on_empty,
            config_label="normalize.take_first",
        )
        if normalized is NORMALIZE_MISS:
            continue
        out[lookup_key] = normalized
    return out


def normalize_take_first_value(
    candidates_obj: RuntimeValue,
    *,
    source_id: str,
    lookup_key: Hashable,
    on_empty: str,
    config_label: str,
) -> RuntimeValue:
    if not _is_sequence(candidates_obj):
        msg = "Source '{}' {} expected list[row] for key '{}', got '{}'".format(
            source_id, config_label, lookup_key, type(candidates_obj).__name__
        )
        raise TypeError(msg)

    candidates = candidates_obj
    if not candidates:
        if on_empty == "miss":
            return NORMALIZE_MISS
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


# ---------------------------------------------------------------------------
# `project_fields`
# ---------------------------------------------------------------------------


def normalize_project_fields(
    result: RuntimeValue,
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
        projected = normalize_project_fields_value(
            row_obj,
            source_id=source_id,
            lookup_key=lookup_key,
            fields=fields,
            on_missing=on_missing,
            config_label="normalize.project_fields",
        )
        out[lookup_key] = projected
    return out


def normalize_project_fields_value(
    row_obj: RuntimeValue,
    *,
    source_id: str,
    lookup_key: Hashable,
    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...],
    on_missing: str,
    config_label: str,
) -> RuntimeValue:
    if not _is_mapping(row_obj):
        msg = "Source '{}' {} expected row to be a Mapping for key '{}', got '{}'".format(
            source_id, config_label, lookup_key, type(row_obj).__name__
        )
        raise TypeError(msg)

    row = row_obj
    projected: Dict[str, RuntimeValue] = {}
    for rule in fields:
        if rule.from_key:
            projected[rule.name] = lookup_key
            continue

        ok, value = extract_segments_with_presence(row, rule.extract_segments)
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


# ---------------------------------------------------------------------------
# `map_values`
# ---------------------------------------------------------------------------


def normalize_map_values(
    result: RuntimeValue,
    *,
    source_id: str,
    steps: Tuple[SourceNormalizeStepIr, ...],
) -> LoaderResultMapping:
    if not _is_hashable_mapping(result):
        msg = "Source '{}' normalize.map_values expected loader result Mapping, got '{}'".format(source_id, type(result).__name__)
        raise TypeError(msg)

    out: LoaderResultMap = {}
    for lookup_key, value in result.items():
        current: RuntimeValue = value
        skip = False
        for idx, step in enumerate(steps):
            current = step.apply_value(current, lookup_key=lookup_key, source_id=source_id, step_index=idx)
            if current is NORMALIZE_MISS:
                skip = True
                break
        if skip:
            continue
        out[lookup_key] = current
    return out


# ---------------------------------------------------------------------------
# 段提取辅助
# ---------------------------------------------------------------------------


def extract_segments_with_presence(
    data: RuntimeValue,
    segments: Tuple[Union[str, int], ...],
) -> Tuple[bool, RuntimeValue]:
    current: RuntimeValue = data
    for segment in segments:
        if current is None:
            return False, None
        ok, current = _extract_segment_with_presence(current, segment)
        if not ok:
            return False, None
    return True, current


def _extract_segment_with_presence(
    data: RuntimeValue,
    segment: Union[str, int],
) -> Tuple[bool, RuntimeValue]:
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
