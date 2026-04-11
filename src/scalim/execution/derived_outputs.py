# pragma: allow-c901-file plan: c60
from __future__ import absolute_import

import hashlib
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from .._internal.utils import graph as graph_utils
from .._internal.utils.converters import auto_str_normalize
from .._internal.utils.iterables import ordered_unique_str
from ..exceptions import ScalimExecutionError
from ..sinks import BaseRowSink, IRowSink
from ..typedefs import FieldValue, KeyNormalizationMode, RowData
from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import dataclass, field
from .key_normalization import normalize_key_normalization


def _auto_str_normalize_derived_key_part(*, value: object, field_id: str, context: str) -> FieldValue:
    if value is None:
        return None
    normalized = auto_str_normalize(value)
    if normalized is None:
        msg = "key_normalization failed for {} key field {!r} (type={})".format(str(context), str(field_id), type(value).__name__)
        raise ValueError(msg)
    return normalized


class ScalimAggregationKeyLimitExceededError(ScalimExecutionError):
    group_count: int
    max_groups: int

    def __init__(self, *, group_count: int, max_groups: int) -> None:
        super(ScalimAggregationKeyLimitExceededError, self).__init__(
            "Group-by key cardinality exceeded: group_count={} > max_groups={}".format(int(group_count), int(max_groups))
        )
        self.group_count = int(group_count)
        self.max_groups = int(max_groups)


class ScalimDistinctKeyLimitExceededError(ScalimExecutionError):
    distinct_count: int
    max_distinct: int
    on_overflow: str
    key_fields: Tuple[str, ...]

    def __init__(
        self,
        *,
        distinct_count: int,
        max_distinct: int,
        on_overflow: str,
        key_fields: Sequence[str],
    ) -> None:
        super(ScalimDistinctKeyLimitExceededError, self).__init__(
            "Distinct key cardinality exceeded: distinct_count={} > max_distinct={} (on_overflow={}, key_fields={})".format(
                int(distinct_count),
                int(max_distinct),
                str(on_overflow),
                ",".join(str(x) for x in key_fields),
            )
        )
        self.distinct_count = int(distinct_count)
        self.max_distinct = int(max_distinct)
        self.on_overflow = str(on_overflow)
        self.key_fields = tuple(str(x) for x in key_fields)


class ScalimDedupKeyConflictError(ScalimExecutionError):
    key_fields: Tuple[str, ...]
    on_conflict: str

    def __init__(self, *, key_fields: Sequence[str], on_conflict: str) -> None:
        super(ScalimDedupKeyConflictError, self).__init__(
            "dedup_by key conflict: on_conflict={!r} requires deterministic resolution; duplicate keys encountered (key_fields={})".format(
                str(on_conflict), ",".join(str(x) for x in key_fields)
            )
        )
        self.key_fields = tuple(str(x) for x in key_fields)
        self.on_conflict = str(on_conflict)


@dataclass
class AggregatorDiagnostics:
    """派生聚合诊断信息(用于 `meta`/`audit`).

    约束:
    - `meta`/`audit_events` 不得包含明细行内容与聚合 `key` 的具体值(避免泄露敏感数据).
    """

    meta: Dict[str, FieldValue] = field(default_factory=dict)
    audit_events: List[Dict[str, FieldValue]] = field(default_factory=list)


class IRowAggregator(ABC):
    """派生聚合器最小接口: 初始化/累计/收尾(对应 `required_fields`/`accumulate`/`finalize_rows`)."""

    @abstractmethod
    def required_fields(self) -> Tuple[str, ...]:
        """返回聚合所需的输入字段列表(来自明细流)."""

    @abstractmethod
    def accumulate(self, row: RowData) -> None:
        """消费一行明细数据,更新聚合状态."""

    @abstractmethod
    def finalize_rows(self) -> List[RowData]:
        """在结束时输出聚合结果行列表."""

    @abstractmethod
    def diagnostics(self) -> AggregatorDiagnostics:
        """返回聚合诊断信息,用于 `meta`/`audit`."""


@dataclass(frozen=True)
class AggMetricSpec:
    """聚合指标定义(内置)."""

    out_field_id: str
    op: str
    field_id: Optional[str] = None
    field_ids: Optional[Tuple[str, ...]] = None
    threshold: Optional[object] = None


@dataclass(frozen=True)
class RankFieldSpec:
    """聚合输出中的排名字段定义(在 `finalize` 阶段计算)."""

    out_field_id: str
    kind: str
    by: str
    partition_by: Tuple[str, ...] = ()
    order: str = "desc"
    order_by: Tuple[str, ...] = ()
    top_k: int = 0
    top_k_mode: str = "rank"


PostFieldCalculator = Callable[[RowData], FieldValue]


@dataclass(frozen=True)
class PostFieldSpec:
    """聚合后派生字段定义(在 `finalize` 阶段计算)."""

    out_field_id: str
    kind: str
    dependencies: Tuple[str, ...]
    fingerprint: str
    calculator: PostFieldCalculator


@dataclass(frozen=True)
class FinalizeDagPlanItem:
    out_field_id: str
    producer_key: str
    dependencies: Tuple[str, ...]
    phase: str


@dataclass(frozen=True)
class FinalizeDagPlan:
    """聚合 `finalize` `DAG` 执行计划(确定性).

    - `items` 使用稳定拓扑序.
    - `phase` 用于在 `top_k/sort` 前后分段执行:
      - `pre_top_k`: 计算 `rank` 字段及其上游依赖(全量行).
      - `post_top_k`: 计算其余派生字段(过滤后行).
    """

    items: Tuple[FinalizeDagPlanItem, ...]

    @property
    def pre_top_k_ids(self) -> Tuple[str, ...]:
        return tuple(item.out_field_id for item in self.items if str(item.phase) == "pre_top_k")

    @property
    def post_top_k_ids(self) -> Tuple[str, ...]:
        return tuple(item.out_field_id for item in self.items if str(item.phase) == "post_top_k")


def build_finalize_dag_plan(*, rank_fields: Sequence[RankFieldSpec], post_fields: Sequence[PostFieldSpec]) -> FinalizeDagPlan:
    """构建 `finalize` `DAG` 计划(稳定拓扑序 + 依赖列表).

    依赖方向约定: A 依赖 B 表示 A -> B, 因此 B 必须在 A 之前计算.
    """

    rank_by_id: Dict[str, RankFieldSpec] = {str(r.out_field_id): r for r in rank_fields}
    post_by_id: Dict[str, PostFieldSpec] = {str(p.out_field_id): p for p in post_fields}

    node_ids: Set[str] = set(rank_by_id.keys()) | set(post_by_id.keys())
    if not node_ids:
        return FinalizeDagPlan(items=())

    deps_by_id: Dict[str, Tuple[str, ...]] = {}
    producer_by_id: Dict[str, str] = {}
    for node_id in node_ids:
        rank_spec = rank_by_id.get(node_id)
        if rank_spec is not None:
            order_fields = tuple(str(x) for x in (rank_spec.order_by or ())) or (str(rank_spec.by),)
            deps = ordered_unique_str((str(rank_spec.by), *tuple(order_fields)))
            deps_by_id[node_id] = deps
            producer_by_id[node_id] = str(rank_spec.kind)
            continue
        post_spec = post_by_id[node_id]
        deps_by_id[node_id] = tuple(str(x) for x in (post_spec.dependencies or ()))
        producer_by_id[node_id] = str(post_spec.kind)

    def _get_derived_deps(node_id: str) -> Tuple[str, ...]:
        raw_deps = deps_by_id.get(str(node_id), ())
        return tuple(d for d in raw_deps if d in node_ids)

    try:
        topo_order = graph_utils.topological_sort(node_ids, _get_derived_deps)
    except graph_utils.ScalimCyclicDependencyError as exc:
        cycles = exc.cycles or ()
        cycle = cycles[0] if cycles else ()
        chain = " -> ".join(str(x) for x in cycle) if cycle else "unknown"
        msg = "Aggregate finalize fields has cyclic dependency: {}".format(chain)
        raise ValueError(msg) from exc

    # `rank_fields` 存在时:
    # - 在 `top_k/sort` 之前计算所有 `rank` 字段及其上游依赖(包含 `rank-after-post` 链路).
    # `rank_fields` 不存在时:
    # - 不存在 `top_k/sort` 阶段,所有派生字段在全量行上计算.
    pre_top_k_set = set(node_ids)
    if rank_by_id:
        pre_top_k_set = graph_utils.collect_dependencies(rank_by_id.keys(), _get_derived_deps, include_target=True)

    # `items` 表示最终“可执行计划”: 先 `pre_top_k`, 再 `post_top_k`, 并保持组内稳定拓扑序.
    ordered_pre = [node_id for node_id in topo_order if node_id in pre_top_k_set]
    ordered_post = [node_id for node_id in topo_order if node_id not in pre_top_k_set]

    items: List[FinalizeDagPlanItem] = []
    for node_id in ordered_pre:
        items.append(
            FinalizeDagPlanItem(
                out_field_id=str(node_id),
                producer_key=producer_by_id.get(str(node_id), ""),
                dependencies=deps_by_id.get(str(node_id), ()),
                phase="pre_top_k",
            )
        )
    for node_id in ordered_post:
        items.append(
            FinalizeDagPlanItem(
                out_field_id=str(node_id),
                producer_key=producer_by_id.get(str(node_id), ""),
                dependencies=deps_by_id.get(str(node_id), ()),
                phase="post_top_k",
            )
        )

    return FinalizeDagPlan(items=tuple(items))


_DECIMAL_ZERO = Decimal(0)
_DECIMAL_ONE = Decimal(1)


def _decimal_from_text(text: str) -> Optional[Decimal]:
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _to_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    dec: Optional[Decimal] = None
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, bool):
        dec = _DECIMAL_ONE if value else _DECIMAL_ZERO
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, float):
        dec = _decimal_from_text(str(value))
    elif isinstance(value, str):
        dec = _decimal_from_text(value.strip())
    if dec is None:
        return None
    if not dec.is_finite():
        return None
    return dec


def _stable_sort_key(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, str):
        return "str:" + value
    if isinstance(value, bool):
        return "bool:" + ("1" if value else "0")
    numeric = _to_decimal(value)
    if numeric is not None:
        return "num:" + format(numeric, "f")
    return "{}:{}".format(type(value).__name__, repr(value))


def _stable_group_key_tuple(key: Tuple[object, ...]) -> str:
    return "\x1f".join(_stable_sort_key(item) for item in key)


class _BoundedDistinctKeySet:
    _keys: Set[Tuple[FieldValue, ...]]
    _max_distinct: int
    _on_overflow: str
    _key_fields: Tuple[str, ...]
    _truncated: bool

    def __init__(self, *, max_distinct: int, on_overflow: str, key_fields: Sequence[str]) -> None:
        self._keys = set()
        self._max_distinct = int(max_distinct) if max_distinct else 0
        self._on_overflow = str(on_overflow or "error").lower()
        self._key_fields = tuple(str(x) for x in key_fields)
        self._truncated = False

    @property
    def max_distinct(self) -> int:
        return int(self._max_distinct)

    @property
    def on_overflow(self) -> str:
        return str(self._on_overflow)

    @property
    def truncated(self) -> bool:
        return bool(self._truncated)

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def add(self, key: Tuple[FieldValue, ...]) -> Tuple[bool, Optional[Tuple[FieldValue, ...]]]:
        """添加去重 `key`.

        返回:
        - `retained`: 新 `key` 是否被纳入状态(截断时可能被丢弃)
        - `removed_key`: 当 `truncate` 且新 `key` 纳入导致替换时,返回被移除的 `key`
        """

        if key in self._keys:
            return False, None

        if not self._max_distinct:
            self._keys.add(key)
            return True, None

        if len(self._keys) < self._max_distinct:
            self._keys.add(key)
            return True, None

        if self._on_overflow == "error":
            raise ScalimDistinctKeyLimitExceededError(
                distinct_count=len(self._keys) + 1,
                max_distinct=self._max_distinct,
                on_overflow=self._on_overflow,
                key_fields=self._key_fields,
            )

        if self._on_overflow != "truncate":
            msg = "Unsupported on_overflow: {!r}".format(self._on_overflow)
            raise ValueError(msg)

        # 在稳定序(按 `_stable_group_key_tuple`)下,仅保留最小的 `max_distinct` 个 `key`.
        worst_key = max(self._keys, key=_stable_group_key_tuple)
        worst_sig = _stable_group_key_tuple(worst_key)
        new_sig = _stable_group_key_tuple(key)

        # 若新 `key` 不优于当前最差 `key`,则直接丢弃.
        if new_sig >= worst_sig:
            self._truncated = True
            return False, None

        self._keys.add(key)
        self._keys.remove(worst_key)
        self._truncated = True
        return True, worst_key


class _MetricState(ABC):
    @abstractmethod
    def accumulate(self, row: RowData) -> None:
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> FieldValue:
        raise NotImplementedError


class _CountMetric(_MetricState):
    _count: int
    _field_id: Optional[str]

    def __init__(self, field_id: Optional[str]) -> None:
        self._count = 0
        self._field_id = field_id

    @override
    def accumulate(self, row: RowData) -> None:
        if self._field_id is None:
            self._count += 1
            return
        if row.get(self._field_id) is not None:
            self._count += 1

    @override
    def finalize(self) -> FieldValue:
        return int(self._count)


class _CountTrueMetric(_MetricState):
    _count: int
    _field_id: str

    def __init__(self, field_id: str) -> None:
        self._count = 0
        self._field_id = str(field_id)

    @override
    def accumulate(self, row: RowData) -> None:
        if bool(row.get(self._field_id)):
            self._count += 1

    @override
    def finalize(self) -> FieldValue:
        return int(self._count)


class _SumMetric(_MetricState):
    _sum: Decimal
    _field_id: str

    def __init__(self, field_id: str) -> None:
        self._sum = _DECIMAL_ZERO
        self._field_id = str(field_id)

    @override
    def accumulate(self, row: RowData) -> None:
        raw = row.get(self._field_id)
        if raw is None:
            return
        dec = _to_decimal(raw)
        if dec is None:
            return
        self._sum += dec

    @override
    def finalize(self) -> FieldValue:
        return self._sum


class _MinMetric(_MetricState):
    _value: FieldValue
    _field_id: str
    _has_value: bool
    _best_key: Optional[Tuple[int, Decimal, str]]

    def __init__(self, field_id: str) -> None:
        self._field_id = str(field_id)
        self._value = None
        self._has_value = False
        self._best_key = None

    @override
    def accumulate(self, row: RowData) -> None:
        raw = row.get(self._field_id)
        if raw is None:
            return
        raw_nn: NonNullFieldValue = raw

        def _cmp_key(v: NonNullFieldValue) -> Tuple[int, Decimal, str]:
            dec = _to_decimal(v)
            if dec is not None:
                return (0, dec, "")
            return (1, _DECIMAL_ZERO, _stable_sort_key(v))

        key = _cmp_key(raw_nn)
        if not self._has_value or self._best_key is None:
            self._value = raw_nn
            self._best_key = key
            self._has_value = True
            return

        if key < self._best_key:
            self._value = raw_nn
            self._best_key = key

    @override
    def finalize(self) -> FieldValue:
        if not self._has_value:
            return None
        return self._value


class _MaxMetric(_MetricState):
    _value: FieldValue
    _field_id: str
    _has_value: bool
    _best_key: Optional[Tuple[int, Decimal, str]]

    def __init__(self, field_id: str) -> None:
        self._field_id = str(field_id)
        self._value = None
        self._has_value = False
        self._best_key = None

    @override
    def accumulate(self, row: RowData) -> None:
        raw = row.get(self._field_id)
        if raw is None:
            return
        raw_nn: NonNullFieldValue = raw

        def _cmp_key(v: NonNullFieldValue) -> Tuple[int, Decimal, str]:
            dec = _to_decimal(v)
            if dec is not None:
                return (0, dec, "")
            return (1, _DECIMAL_ZERO, _stable_sort_key(v))

        key = _cmp_key(raw_nn)
        if not self._has_value or self._best_key is None:
            self._value = raw_nn
            self._best_key = key
            self._has_value = True
            return

        if key > self._best_key:
            self._value = raw_nn
            self._best_key = key

    @override
    def finalize(self) -> FieldValue:
        if not self._has_value:
            return None
        return self._value


class _CountDistinctMetric(_MetricState):
    _field_ids: Tuple[str, ...]
    _distinct: _BoundedDistinctKeySet

    def __init__(self, *, field_ids: Sequence[str], max_distinct: int, on_overflow: str) -> None:
        ids = [str(x) for x in field_ids if str(x)]
        if not ids:
            msg = "count_distinct requires field_id(s)"
            raise ValueError(msg)
        self._field_ids = tuple(ids)
        self._distinct = _BoundedDistinctKeySet(
            max_distinct=int(max_distinct),
            on_overflow=str(on_overflow),
            key_fields=self._field_ids,
        )

    @property
    def truncated(self) -> bool:
        return bool(self._distinct.truncated)

    @property
    def key_count(self) -> int:
        return int(self._distinct.key_count)

    @override
    def accumulate(self, row: RowData) -> None:
        key = tuple(row.get(fid) for fid in self._field_ids)
        # 对齐 `SQL` `COUNT(DISTINCT)` 的 `NULL` 语义: 任一组成字段为 `None` 则忽略该行.
        if any(v is None for v in key):
            return
        _ = self._distinct.add(key)

    @override
    def finalize(self) -> FieldValue:
        return int(self._distinct.key_count)


class _CountTrueGteMetric(_MetricState):
    _count: int
    _field_id: str
    _threshold: Decimal

    def __init__(self, *, field_id: str, threshold: object) -> None:
        self._count = 0
        self._field_id = str(field_id)
        dec = _to_decimal(threshold)
        if dec is None:
            msg = "count_true_gte requires numeric threshold"
            raise ValueError(msg)
        self._threshold = dec

    @override
    def accumulate(self, row: RowData) -> None:
        raw = row.get(self._field_id)
        if raw is None:
            return
        dec = _to_decimal(raw)
        if dec is None:
            return
        if dec >= self._threshold:
            self._count += 1

    @override
    def finalize(self) -> FieldValue:
        return int(self._count)


def _metric_state_count(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    _ = max_distinct, on_overflow
    return _CountMetric(spec.field_id)


def _metric_state_count_true(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    _ = max_distinct, on_overflow
    if not spec.field_id:
        msg = "count_true requires field_id"
        raise ValueError(msg)
    return _CountTrueMetric(spec.field_id)


def _metric_state_sum(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    _ = max_distinct, on_overflow
    if not spec.field_id:
        msg = "sum requires field_id"
        raise ValueError(msg)
    return _SumMetric(spec.field_id)


def _metric_state_min(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    _ = max_distinct, on_overflow
    if not spec.field_id:
        msg = "min requires field_id"
        raise ValueError(msg)
    return _MinMetric(spec.field_id)


def _metric_state_max(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    _ = max_distinct, on_overflow
    if not spec.field_id:
        msg = "max requires field_id"
        raise ValueError(msg)
    return _MaxMetric(spec.field_id)


def _metric_state_count_distinct(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    if spec.field_id and spec.field_ids:
        msg = "count_distinct does not allow both field_id and field_ids"
        raise ValueError(msg)
    if spec.field_id:
        return _CountDistinctMetric(field_ids=(str(spec.field_id),), max_distinct=max_distinct, on_overflow=on_overflow)
    if spec.field_ids:
        return _CountDistinctMetric(field_ids=tuple(str(x) for x in spec.field_ids), max_distinct=max_distinct, on_overflow=on_overflow)
    msg = "count_distinct requires field_id or field_ids"
    raise ValueError(msg)


def _metric_state_count_true_gte(spec: AggMetricSpec, *, max_distinct: int, on_overflow: str) -> _MetricState:
    _ = max_distinct, on_overflow
    if not spec.field_id:
        msg = "count_true_gte requires field_id"
        raise ValueError(msg)
    if spec.threshold is None:
        msg = "count_true_gte requires threshold"
        raise ValueError(msg)
    return _CountTrueGteMetric(field_id=str(spec.field_id), threshold=spec.threshold)


_METRIC_STATE_FACTORY_BY_OP = {
    "count": _metric_state_count,
    "count_distinct": _metric_state_count_distinct,
    "count_true": _metric_state_count_true,
    "count_true_gte": _metric_state_count_true_gte,
    "max": _metric_state_max,
    "min": _metric_state_min,
    "sum": _metric_state_sum,
}


def _metric_state_from_spec(spec: AggMetricSpec, *, max_distinct: int = 0, on_overflow: str = "error") -> _MetricState:
    op = str(spec.op).lower()
    factory = _METRIC_STATE_FACTORY_BY_OP.get(op)
    if factory is None:
        msg = "Unsupported aggregation op: {!r}".format(spec.op)
        raise ValueError(msg)
    return factory(spec, max_distinct=max_distinct, on_overflow=on_overflow)


class GroupByAggregator(IRowAggregator):
    _group_by: Tuple[str, ...]
    _metrics: Tuple[AggMetricSpec, ...]
    _states: Dict[Tuple[FieldValue, ...], Tuple[_MetricState, ...]]
    _max_groups: int
    _max_distinct: int
    _distinct_on_overflow: str
    _key_normalization: KeyNormalizationMode

    def __init__(
        self,
        *,
        group_by: Sequence[str],
        metrics: Sequence[AggMetricSpec],
        max_groups: int = 0,
        max_distinct: int = 0,
        distinct_on_overflow: str = "error",
        key_normalization: KeyNormalizationMode = "raw",
    ) -> None:
        if not group_by:
            msg = "group_by cannot be empty"
            raise ValueError(msg)
        if not metrics:
            msg = "metrics cannot be empty"
            raise ValueError(msg)
        self._group_by = tuple(str(item) for item in group_by)
        self._metrics = tuple(metrics)
        self._states = {}
        self._max_groups = int(max_groups) if max_groups else 0
        self._max_distinct = int(max_distinct) if max_distinct else 0
        self._distinct_on_overflow = str(distinct_on_overflow or "error").lower()
        self._key_normalization = normalize_key_normalization(key_normalization)

    @override
    def required_fields(self) -> Tuple[str, ...]:
        required: List[str] = list(self._group_by)
        for m in self._metrics:
            if m.field_id:
                required.append(str(m.field_id))
            if m.field_ids:
                required.extend([str(x) for x in m.field_ids])
        # 去重但保留顺序.
        seen: Set[str] = set()
        ordered: List[str] = []
        for fid in required:
            if fid in seen:
                continue
            seen.add(fid)
            ordered.append(fid)
        return tuple(ordered)

    @override
    def accumulate(self, row: RowData) -> None:
        if self._key_normalization == "raw":
            key = tuple(row.get(fid) for fid in self._group_by)
        else:
            key = tuple(
                _auto_str_normalize_derived_key_part(value=row.get(fid), field_id=fid, context="group_by") for fid in self._group_by
            )
        state = self._states.get(key)
        if state is None:
            if self._max_groups and len(self._states) >= self._max_groups:
                raise ScalimAggregationKeyLimitExceededError(group_count=len(self._states) + 1, max_groups=self._max_groups)
            state = tuple(
                _metric_state_from_spec(m, max_distinct=self._max_distinct, on_overflow=self._distinct_on_overflow) for m in self._metrics
            )
            self._states[key] = state
        for metric in state:
            metric.accumulate(row)

    @override
    def finalize_rows(self) -> List[RowData]:
        rows: List[RowData] = []
        sorted_keys = sorted(self._states.keys(), key=_stable_group_key_tuple)
        for key in sorted_keys:
            state = self._states[key]
            out: Dict[str, FieldValue] = {}
            for idx, fid in enumerate(self._group_by):
                out[fid] = key[idx] if idx < len(key) else None
            for metric_spec, metric_state in zip(self._metrics, state):
                out[str(metric_spec.out_field_id)] = metric_state.finalize()
            rows.append(out)
        return rows

    @override
    def diagnostics(self) -> AggregatorDiagnostics:
        meta: Dict[str, FieldValue] = {"group_count": len(self._states)}
        audit_events: List[Dict[str, FieldValue]] = []

        distinct_indices = [i for i, m in enumerate(self._metrics) if str(m.op).lower() == "count_distinct"]
        for idx in distinct_indices:
            out_field = str(self._metrics[idx].out_field_id)
            total_keys = 0
            max_keys_per_group = 0
            truncated_groups = 0
            for state in self._states.values():
                metric_state = state[idx]
                if not isinstance(metric_state, _CountDistinctMetric):
                    continue
                total_keys += int(metric_state.key_count)
                max_keys_per_group = max(max_keys_per_group, int(metric_state.key_count))
                if metric_state.truncated:
                    truncated_groups += 1

            meta["metric.{}.distinct_keys_total".format(out_field)] = int(total_keys)
            meta["metric.{}.distinct_keys_max_per_group".format(out_field)] = int(max_keys_per_group)
            meta["metric.{}.distinct_truncated_groups".format(out_field)] = int(truncated_groups)

            if truncated_groups:
                audit_events.append(
                    {
                        "event_type": "distinct_truncated",
                        "message": "count_distinct truncated: metric={}, truncated_groups={}, max_distinct={}, on_overflow={}".format(
                            out_field,
                            int(truncated_groups),
                            int(self._max_distinct),
                            str(self._distinct_on_overflow),
                        ),
                    }
                )

        return AggregatorDiagnostics(meta=meta, audit_events=audit_events)


class RankedGroupByAggregator(IRowAggregator):
    """`GroupBy` + `finalize` 阶段排名/派生字段.

    约束:
    - 排名与聚合后派生字段仅在 `finalize` 阶段执行(单线程),用于保持结果确定性.
    - 输出稳定性: 当 `order_by` 不足以区分行时,以 `group_by` 键的稳定字符串键作为最后的 `tie-break`.
    """

    _base: GroupByAggregator
    _group_by: Tuple[str, ...]
    _rank_fields: Tuple[RankFieldSpec, ...]
    _post_fields: Tuple[PostFieldSpec, ...]
    _finalize_plan: FinalizeDagPlan

    def __init__(
        self,
        *,
        group_by: Sequence[str],
        metrics: Sequence[AggMetricSpec],
        rank_fields: Sequence[RankFieldSpec] = (),
        post_fields: Sequence[PostFieldSpec] = (),
        max_groups: int = 0,
        max_distinct: int = 0,
        distinct_on_overflow: str = "error",
        key_normalization: KeyNormalizationMode = "raw",
    ) -> None:
        self._group_by = tuple(str(item) for item in group_by)
        self._rank_fields = tuple(rank_fields)
        self._post_fields = tuple(post_fields)
        self._finalize_plan = build_finalize_dag_plan(rank_fields=self._rank_fields, post_fields=self._post_fields)
        self._base = GroupByAggregator(
            group_by=self._group_by,
            metrics=metrics,
            max_groups=max_groups,
            max_distinct=max_distinct,
            distinct_on_overflow=distinct_on_overflow,
            key_normalization=key_normalization,
        )

    @override
    def required_fields(self) -> Tuple[str, ...]:
        return self._base.required_fields()

    @override
    def accumulate(self, row: RowData) -> None:
        self._base.accumulate(row)

    @override
    def finalize_rows(self) -> List[RowData]:  # noqa: C901
        rows: List[Dict[str, FieldValue]] = [dict(r) for r in self._base.finalize_rows()]
        if not rows:
            return []

        rank_by_id: Dict[str, RankFieldSpec] = {str(r.out_field_id): r for r in self._rank_fields}
        post_by_id: Dict[str, PostFieldSpec] = {str(p.out_field_id): p for p in self._post_fields}

        for fid in self._finalize_plan.pre_top_k_ids:
            rank_spec = rank_by_id.get(str(fid))
            if rank_spec is not None:
                self._apply_rank_field(rows, rank_spec)
                continue

            post_spec = post_by_id.get(str(fid))
            if (
                post_spec is None
            ):  # pragma: no cover  # pragma: allow-no-cover invariant: finalize plan ids are derived from rank/post specs
                msg = "Unknown finalize field id: {!r}".format(fid)
                raise ValueError(msg)
            out_key = str(post_spec.out_field_id)
            for row in rows:
                row[out_key] = post_spec.calculator(row)

        primary_rank = self._select_primary_rank_spec()
        if primary_rank is not None:
            rows = self._apply_top_k_and_sort(rows, primary_rank)

        for fid in self._finalize_plan.post_top_k_ids:
            rank_spec = rank_by_id.get(str(fid))
            if rank_spec is not None:  # pragma: no cover  # pragma: allow-no-cover invariant: post_top_k ids should refer to post specs
                self._apply_rank_field(rows, rank_spec)
                continue

            post_spec = post_by_id.get(str(fid))
            if (
                post_spec is None
            ):  # pragma: no cover  # pragma: allow-no-cover invariant: finalize plan ids are derived from rank/post specs
                msg = "Unknown finalize field id: {!r}".format(fid)
                raise ValueError(msg)
            out_key = str(post_spec.out_field_id)
            for row in rows:
                row[out_key] = post_spec.calculator(row)

        return list(rows)

    def _select_primary_rank_spec(self) -> Optional[RankFieldSpec]:
        if not self._rank_fields:
            return None
        with_top_k = [r for r in self._rank_fields if int(r.top_k) > 0]
        if with_top_k:
            return with_top_k[0]
        # 按 `out_field_id` 稳定选择一个,用于稳定输出顺序.
        return sorted(self._rank_fields, key=lambda r: str(r.out_field_id))[0]

    def _apply_top_k_and_sort(self, rows: List[Dict[str, FieldValue]], spec: RankFieldSpec) -> List[Dict[str, FieldValue]]:
        partitions: Dict[Tuple[FieldValue, ...], List[Dict[str, FieldValue]]] = {}
        for row in rows:
            key = self._partition_key(row, spec)
            partitions.setdefault(key, []).append(row)

        ordered: List[Dict[str, FieldValue]] = []
        for p_key in sorted(partitions.keys(), key=_stable_group_key_tuple):
            bucket = partitions[p_key]
            bucket.sort(key=lambda r: self._row_sort_key(r, spec))
            if int(spec.top_k) > 0:
                k = int(spec.top_k)
                if str(spec.top_k_mode or "rank").lower() == "rows":
                    bucket = bucket[:k]
                else:
                    out_key = str(spec.out_field_id)
                    bucket = [r for r in bucket if int(r.get(out_key) or 0) <= k]
            ordered.extend(bucket)

        return ordered

    def _partition_key(self, row: Dict[str, FieldValue], spec: RankFieldSpec) -> Tuple[FieldValue, ...]:
        if not spec.partition_by:
            return ()
        return tuple(row.get(str(fid)) for fid in spec.partition_by)

    def _row_sort_key(self, row: Dict[str, FieldValue], spec: RankFieldSpec) -> Tuple[object, ...]:
        desc = str(spec.order or "desc").lower() != "asc"
        order_fields = tuple(str(x) for x in (spec.order_by or ())) or (str(spec.by),)
        key_parts: List[object] = []
        for fid in order_fields:
            key_parts.extend(self._value_sort_key(row.get(fid), desc=desc))
        group_key = tuple(row.get(fid) for fid in self._group_by)
        key_parts.append(_stable_group_key_tuple(group_key))
        return tuple(key_parts)

    def _value_sort_key(self, value: object, *, desc: bool) -> Tuple[int, int, "_ReversibleValue"]:
        # `None` 永远排在最后;其余尽量按数值排序(失败时回退为稳定字符串键).
        if value is None:
            return (1, 0, _ReversibleValue(_DECIMAL_ZERO, desc=False))
        dec = _to_decimal(value)
        if dec is not None:
            return (0, 0, _ReversibleValue(dec, desc=desc))
        return (0, 1, _ReversibleValue(_stable_sort_key(value), desc=desc))

    def _apply_rank_field(self, rows: List[Dict[str, FieldValue]], spec: RankFieldSpec) -> None:
        partitions: Dict[Tuple[FieldValue, ...], List[Dict[str, FieldValue]]] = {}
        for row in rows:
            key = self._partition_key(row, spec)
            partitions.setdefault(key, []).append(row)

        kind = str(spec.kind or "").strip()
        out_key = str(spec.out_field_id)
        by_key = str(spec.by)

        for p_key in sorted(partitions.keys(), key=_stable_group_key_tuple):
            bucket = partitions[p_key]
            bucket.sort(key=lambda r: self._row_sort_key(r, spec))
            if kind == "row_number":
                for idx, row in enumerate(bucket):
                    row[out_key] = int(idx) + 1
                continue

            prev_sig = None
            last_rank = 0
            for idx, row in enumerate(bucket):
                sig = _stable_sort_key(row.get(by_key))
                if idx == 0:
                    last_rank = 1
                elif sig != prev_sig:
                    if kind == "rank":
                        last_rank = int(idx) + 1
                    else:
                        last_rank += 1
                row[out_key] = int(last_rank)
                prev_sig = sig

    @override
    def diagnostics(self) -> AggregatorDiagnostics:
        return self._base.diagnostics()


class _ReversibleValue:
    desc: bool
    value: Union[Decimal, str]

    __slots__: Tuple[str, str] = ("desc", "value")

    def __init__(self, value: Union[Decimal, str], *, desc: bool) -> None:
        self.value = value
        self.desc = bool(desc)

    @override
    def __hash__(self) -> int:
        return hash((self.desc, self.value))

    def __lt__(self, other: object) -> bool:
        if not isinstance(
            other, _ReversibleValue
        ):  # pragma: no cover  # pragma: allow-no-cover defensive: rich comparison protocol fallback
            return NotImplemented  # type: ignore[return-value]
        if isinstance(self.value, Decimal) and isinstance(other.value, Decimal):  # noqa: SIM114
            result = other.value < self.value if self.desc else self.value < other.value
        elif isinstance(self.value, str) and isinstance(other.value, str):
            result = other.value < self.value if self.desc else self.value < other.value
        else:
            # 防御性兜底: 理论上不会发生(由 `_value_sort_key` 保证类型一致),但这里仍保持确定性.
            left = "{}:{}".format(type(self.value).__name__, str(self.value))
            right = "{}:{}".format(type(other.value).__name__, str(other.value))
            result = right < left if self.desc else left < right
        return bool(result)

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(
            other, _ReversibleValue
        ):  # pragma: no cover  # pragma: allow-no-cover defensive: rich comparison protocol fallback
            return False
        return bool(self.desc) == bool(other.desc) and self.value == other.value


class DedupByThenAggregator(IRowAggregator):
    _key_fields: Tuple[str, ...]
    _on_conflict: str
    _distinct: _BoundedDistinctKeySet
    _downstream: IRowAggregator
    _store_fields: Tuple[str, ...]
    _rows: Dict[Tuple[FieldValue, ...], Dict[str, FieldValue]]
    _conflict_count: int
    _key_normalization: KeyNormalizationMode

    def __init__(
        self,
        *,
        key_fields: Sequence[str],
        on_conflict: str,
        max_distinct: int,
        on_overflow: str,
        downstream: IRowAggregator,
        key_normalization: KeyNormalizationMode = "raw",
    ) -> None:
        ids = [str(x) for x in key_fields if str(x)]
        if not ids:
            msg = "dedup_by requires key_fields"
            raise ValueError(msg)
        self._key_fields = tuple(ids)
        self._on_conflict = str(on_conflict or "error").lower()
        if self._on_conflict not in ("error", "first", "last"):
            msg = "Unsupported dedup_by.on_conflict: {!r}".format(on_conflict)
            raise ValueError(msg)

        self._distinct = _BoundedDistinctKeySet(
            max_distinct=int(max_distinct),
            on_overflow=str(on_overflow or "error"),
            key_fields=self._key_fields,
        )
        self._downstream = downstream
        store_fields: List[str] = list(self._key_fields) + list(downstream.required_fields())
        # 去重但保留顺序.
        seen: Set[str] = set()
        ordered: List[str] = []
        for fid in store_fields:
            if fid in seen:
                continue
            seen.add(fid)
            ordered.append(fid)
        self._store_fields = tuple(ordered)

        self._rows = {}
        self._conflict_count = 0
        self._key_normalization = normalize_key_normalization(key_normalization)

    @override
    def required_fields(self) -> Tuple[str, ...]:
        return self._store_fields

    @override
    def accumulate(self, row: RowData) -> None:
        if self._key_normalization == "raw":
            key = tuple(row.get(fid) for fid in self._key_fields)
            stored_row = {fid: row.get(fid) for fid in self._store_fields}
        else:
            normalized_by_fid: Dict[str, FieldValue] = {}
            parts: List[FieldValue] = []
            for fid in self._key_fields:
                normalized_part = _auto_str_normalize_derived_key_part(value=row.get(fid), field_id=fid, context="dedup_by")
                normalized_by_fid[fid] = normalized_part
                parts.append(normalized_part)
            key = tuple(parts)
            stored_row = {fid: (normalized_by_fid[fid] if fid in normalized_by_fid else row.get(fid)) for fid in self._store_fields}
        existing = self._rows.get(key)
        if existing is not None:
            self._conflict_count += 1
            if self._on_conflict == "error":
                raise ScalimDedupKeyConflictError(key_fields=self._key_fields, on_conflict=self._on_conflict)
            if self._on_conflict == "last":
                self._rows[key] = stored_row
            # `first`: 保留已有行
            return

        retained, removed = self._distinct.add(key)
        if removed is not None:
            _ = self._rows.pop(removed, None)
        if not retained:
            return

        self._rows[key] = stored_row

    @override
    def finalize_rows(self) -> List[RowData]:
        # 将 `dedup_by` 后的“实体行”按稳定顺序喂给下游聚合器,确保对拍友好.
        for key in sorted(self._rows.keys(), key=_stable_group_key_tuple):
            self._downstream.accumulate(self._rows[key])
        return self._downstream.finalize_rows()

    @override
    def diagnostics(self) -> AggregatorDiagnostics:
        diag = self._downstream.diagnostics()
        meta = dict(diag.meta)
        audit_events = list(diag.audit_events)

        meta["dedup.key_count"] = int(self._distinct.key_count)
        meta["dedup.truncated"] = bool(self._distinct.truncated)
        meta["dedup.conflict_count"] = int(self._conflict_count)

        if self._distinct.truncated:
            audit_events.append(
                {
                    "event_type": "dedup_truncated",
                    "message": "dedup_by truncated: key_count_kept={}, max_distinct={}, on_overflow={}".format(
                        int(self._distinct.key_count),
                        int(self._distinct.max_distinct),
                        str(self._distinct.on_overflow),
                    ),
                }
            )

        return AggregatorDiagnostics(meta=meta, audit_events=audit_events)


class TwoStageGroupByAggregator(IRowAggregator):
    _stage1: GroupByAggregator
    _stage2: GroupByAggregator

    def __init__(self, *, stage1: GroupByAggregator, stage2: GroupByAggregator) -> None:
        self._stage1 = stage1
        self._stage2 = stage2

    @override
    def required_fields(self) -> Tuple[str, ...]:
        return self._stage1.required_fields()

    @override
    def accumulate(self, row: RowData) -> None:
        self._stage1.accumulate(row)

    @override
    def finalize_rows(self) -> List[RowData]:
        rows1 = self._stage1.finalize_rows()
        for row in rows1:
            self._stage2.accumulate(row)
        return self._stage2.finalize_rows()

    @override
    def diagnostics(self) -> AggregatorDiagnostics:
        diag1 = self._stage1.diagnostics()
        diag2 = self._stage2.diagnostics()

        meta: Dict[str, FieldValue] = {}
        for k, v in diag1.meta.items():
            meta["stage1." + str(k)] = v
        for k, v in diag2.meta.items():
            meta["stage2." + str(k)] = v

        audit_events = list(diag1.audit_events) + list(diag2.audit_events)
        return AggregatorDiagnostics(meta=meta, audit_events=audit_events)


class AggregatingRowSink(BaseRowSink):
    """将 `IRowAggregator` 适配为 `IRowSink`.

    - `write_row`: 仅做累计(调用 `accumulate`)
    - `close`: `finalize_rows` 后调用下游 `sink` 的 `write_batch`/`close`
    """

    _aggregator: IRowAggregator
    _out_sink: IRowSink
    _closed: bool

    def __init__(self, *, aggregator: IRowAggregator, out_sink: IRowSink) -> None:
        self._aggregator = aggregator
        self._out_sink = out_sink
        self._closed = False

    @property
    def aggregator(self) -> IRowAggregator:
        return self._aggregator

    @property
    def out_sink(self) -> IRowSink:
        return self._out_sink

    @override
    def write_row(self, row: RowData) -> None:
        if self._closed:
            msg = "AggregatingRowSink is closed"
            raise RuntimeError(msg)
        self._aggregator.accumulate(row)

    @override
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            rows = self._aggregator.finalize_rows()
            self._out_sink.write_batch(rows)
        finally:
            self._out_sink.close()


def fingerprint_for_meta(
    *,
    demand_name: str,
    main_source_id: str,
    target_fields: Sequence[str],
    field_specs: Iterable[Tuple[str, str, str, str]],
) -> str:
    """生成稳定的元信息指纹(用于对拍/诊断).

    该指纹刻意不包含可调用对象(`callable`),以保持跨进程/跨环境稳定.
    """

    h = hashlib.sha1()  # noqa: S324
    payload = "\n".join(
        [
            "demand_name=" + str(demand_name),
            "main_source_id=" + str(main_source_id),
            "targets=" + ",".join(str(x) for x in target_fields),
            "fields=",
            *("  " + "|".join(parts) for parts in field_specs),
        ]
    ).encode("utf-8")
    h.update(payload)
    return h.hexdigest()


NonNullFieldValue = Union[int, float, Decimal, str, bool]

__all__ = ()
