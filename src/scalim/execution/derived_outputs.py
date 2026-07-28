# pragma: allow-c901-file plan: c60
from __future__ import absolute_import

import hashlib
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union, cast

from .._internal.utils import graph as graph_utils
from .._internal.utils.converters import auto_str_normalize
from .._internal.utils.iterables import ordered_unique_str
from ..sinks import BaseRowSink, IRowSink
from ..typedefs import CellValue, FieldValue, KeyNormalizationMode, RowData, RuntimeValue
from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import dataclass, field
from .key_normalization import normalize_key_normalization


def _auto_str_normalize_derived_key_part(*, value: RuntimeValue, field_id: str, context: str) -> FieldValue:
    if value is None:
        return None
    normalized = auto_str_normalize(value)
    if normalized is None:
        msg = "key_normalization failed for {} key field {!r} (type={})".format(str(context), str(field_id), type(value).__name__)
        raise ValueError(msg)
    return normalized


def _cell_value_as_int(value: CellValue) -> int:
    """将 `sink` 单元格值转为 `int`,供 `rank`/`top_k` 过滤使用."""
    return int(cast("Any", value or 0))  # pragma: allow-cast CellValue → int for rank/top_k


@dataclass
class AggregatorDiagnostics:
    """派生聚合诊断信息(用于 `meta`/`audit`).

    约束:
    - `meta`/`audit_events` 不得包含明细行内容与聚合 `key` 的具体值(避免泄露敏感数据).
    """

    meta: Dict[str, CellValue] = field(default_factory=dict)
    audit_events: List[Dict[str, CellValue]] = field(default_factory=list)


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
    threshold: Optional[RuntimeValue] = None


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


PostFieldCalculator = Callable[[RowData], CellValue]


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


def _to_decimal(value: RuntimeValue) -> Optional[Decimal]:
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


def _stable_sort_key(value: RuntimeValue) -> str:
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


def _stable_group_key_tuple(key: Tuple[RuntimeValue, ...]) -> str:
    return "\x1f".join(_stable_sort_key(item) for item in key)


class _MetricState(ABC):
    @abstractmethod
    def accumulate(self, row: RowData) -> None:
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> CellValue:
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
    def finalize(self) -> CellValue:
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
    def finalize(self) -> CellValue:
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
    def finalize(self) -> CellValue:
        return self._sum


class _MinMetric(_MetricState):
    _value: CellValue
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

        def _cmp_key(v: RuntimeValue) -> Tuple[int, Decimal, str]:
            dec = _to_decimal(v)
            if dec is not None:
                return (0, dec, "")
            return (1, _DECIMAL_ZERO, _stable_sort_key(v))

        key = _cmp_key(raw)
        if not self._has_value or self._best_key is None:
            self._value = raw
            self._best_key = key
            self._has_value = True
            return

        if key < self._best_key:
            self._value = raw
            self._best_key = key

    @override
    def finalize(self) -> CellValue:
        if not self._has_value:
            return None
        return self._value


class _MaxMetric(_MetricState):
    _value: CellValue
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

        def _cmp_key(v: RuntimeValue) -> Tuple[int, Decimal, str]:
            dec = _to_decimal(v)
            if dec is not None:
                return (0, dec, "")
            return (1, _DECIMAL_ZERO, _stable_sort_key(v))

        key = _cmp_key(raw)
        if not self._has_value or self._best_key is None:
            self._value = raw
            self._best_key = key
            self._has_value = True
            return

        if key > self._best_key:
            self._value = raw
            self._best_key = key

    @override
    def finalize(self) -> CellValue:
        if not self._has_value:
            return None
        return self._value


class _CountDistinctMetric(_MetricState):
    _field_ids: Tuple[str, ...]
    _distinct: Set[Tuple[CellValue, ...]]

    def __init__(self, *, field_ids: Sequence[str]) -> None:
        ids = [str(x) for x in field_ids if str(x)]
        if not ids:
            msg = "count_distinct requires field_id(s)"
            raise ValueError(msg)
        self._field_ids = tuple(ids)
        self._distinct = set()

    @property
    def key_count(self) -> int:
        return len(self._distinct)

    @override
    def accumulate(self, row: RowData) -> None:
        key = tuple(row.get(fid) for fid in self._field_ids)
        # 对齐 `SQL` `COUNT(DISTINCT)` 的 `NULL` 语义: 任一组成字段为 `None` 则忽略该行.
        if any(v is None for v in key):
            return
        self._distinct.add(key)

    @override
    def finalize(self) -> CellValue:
        return len(self._distinct)


class _CountTrueGteMetric(_MetricState):
    _count: int
    _field_id: str
    _threshold: Decimal

    def __init__(self, *, field_id: str, threshold: RuntimeValue) -> None:
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
    def finalize(self) -> CellValue:
        return int(self._count)


def _metric_state_count(spec: AggMetricSpec) -> _MetricState:
    return _CountMetric(spec.field_id)


def _metric_state_count_true(spec: AggMetricSpec) -> _MetricState:
    if not spec.field_id:
        msg = "count_true requires field_id"
        raise ValueError(msg)
    return _CountTrueMetric(spec.field_id)


def _metric_state_sum(spec: AggMetricSpec) -> _MetricState:
    if not spec.field_id:
        msg = "sum requires field_id"
        raise ValueError(msg)
    return _SumMetric(spec.field_id)


def _metric_state_min(spec: AggMetricSpec) -> _MetricState:
    if not spec.field_id:
        msg = "min requires field_id"
        raise ValueError(msg)
    return _MinMetric(spec.field_id)


def _metric_state_max(spec: AggMetricSpec) -> _MetricState:
    if not spec.field_id:
        msg = "max requires field_id"
        raise ValueError(msg)
    return _MaxMetric(spec.field_id)


def _metric_state_count_distinct(spec: AggMetricSpec) -> _MetricState:
    if spec.field_id and spec.field_ids:
        msg = "count_distinct does not allow both field_id and field_ids"
        raise ValueError(msg)
    if spec.field_id:
        return _CountDistinctMetric(field_ids=(str(spec.field_id),))
    if spec.field_ids:
        return _CountDistinctMetric(field_ids=tuple(str(x) for x in spec.field_ids))
    msg = "count_distinct requires field_id or field_ids"
    raise ValueError(msg)


def _metric_state_count_true_gte(spec: AggMetricSpec) -> _MetricState:
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


def _metric_state_from_spec(spec: AggMetricSpec) -> _MetricState:
    op = str(spec.op).lower()
    factory = _METRIC_STATE_FACTORY_BY_OP.get(op)
    if factory is None:
        msg = "Unsupported aggregation op: {!r}".format(spec.op)
        raise ValueError(msg)
    return factory(spec)


class GroupByAggregator(IRowAggregator):
    _group_by: Tuple[str, ...]
    _metrics: Tuple[AggMetricSpec, ...]
    _states: Dict[Tuple[CellValue, ...], Tuple[_MetricState, ...]]
    _key_normalization: KeyNormalizationMode

    def __init__(
        self,
        *,
        group_by: Sequence[str],
        metrics: Sequence[AggMetricSpec],
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
            state = tuple(_metric_state_from_spec(m) for m in self._metrics)
            self._states[key] = state
        for metric in state:
            metric.accumulate(row)

    @override
    def finalize_rows(self) -> List[RowData]:
        rows: List[RowData] = []
        sorted_keys = sorted(self._states.keys(), key=_stable_group_key_tuple)
        for key in sorted_keys:
            state = self._states[key]
            out: Dict[str, CellValue] = {}
            for idx, fid in enumerate(self._group_by):
                out[fid] = key[idx] if idx < len(key) else None
            for metric_spec, metric_state in zip(self._metrics, state):
                out[str(metric_spec.out_field_id)] = metric_state.finalize()
            rows.append(out)
        return rows

    @override
    def diagnostics(self) -> AggregatorDiagnostics:
        meta: Dict[str, CellValue] = {"group_count": len(self._states)}
        audit_events: List[Dict[str, CellValue]] = []

        distinct_indices = [i for i, m in enumerate(self._metrics) if str(m.op).lower() == "count_distinct"]
        for idx in distinct_indices:
            out_field = str(self._metrics[idx].out_field_id)
            total_keys = 0
            max_keys_per_group = 0
            for state in self._states.values():
                metric_state = state[idx]
                if not isinstance(metric_state, _CountDistinctMetric):
                    continue
                total_keys += int(metric_state.key_count)
                max_keys_per_group = max(max_keys_per_group, int(metric_state.key_count))

            meta["metric.{}.distinct_keys_total".format(out_field)] = int(total_keys)
            meta["metric.{}.distinct_keys_max_per_group".format(out_field)] = int(max_keys_per_group)

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
        key_normalization: KeyNormalizationMode = "raw",
    ) -> None:
        self._group_by = tuple(str(item) for item in group_by)
        self._rank_fields = tuple(rank_fields)
        self._post_fields = tuple(post_fields)
        self._finalize_plan = build_finalize_dag_plan(rank_fields=self._rank_fields, post_fields=self._post_fields)
        self._base = GroupByAggregator(
            group_by=self._group_by,
            metrics=metrics,
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
        rows: List[Dict[str, CellValue]] = [dict(r) for r in self._base.finalize_rows()]
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

    def _apply_top_k_and_sort(self, rows: List[Dict[str, CellValue]], spec: RankFieldSpec) -> List[Dict[str, CellValue]]:
        partitions: Dict[Tuple[CellValue, ...], List[Dict[str, CellValue]]] = {}
        for row in rows:
            key = self._partition_key(row, spec)
            partitions.setdefault(key, []).append(row)

        ordered: List[Dict[str, CellValue]] = []
        for p_key in sorted(partitions.keys(), key=_stable_group_key_tuple):
            bucket = partitions[p_key]
            bucket.sort(key=lambda r: self._row_sort_key(r, spec))
            if int(spec.top_k) > 0:
                k = int(spec.top_k)
                if str(spec.top_k_mode or "rank").lower() == "rows":
                    bucket = bucket[:k]
                else:
                    out_key = str(spec.out_field_id)
                    bucket = [r for r in bucket if _cell_value_as_int(r.get(out_key)) <= k]
            ordered.extend(bucket)

        return ordered

    def _partition_key(self, row: Dict[str, CellValue], spec: RankFieldSpec) -> Tuple[CellValue, ...]:
        if not spec.partition_by:
            return ()
        return tuple(row.get(str(fid)) for fid in spec.partition_by)

    def _row_sort_key(self, row: Dict[str, CellValue], spec: RankFieldSpec) -> Tuple[RuntimeValue, ...]:
        desc = str(spec.order or "desc").lower() != "asc"
        order_fields = tuple(str(x) for x in (spec.order_by or ())) or (str(spec.by),)
        key_parts: List[RuntimeValue] = []
        for fid in order_fields:
            key_parts.extend(self._value_sort_key(row.get(fid), desc=desc))
        group_key = tuple(row.get(fid) for fid in self._group_by)
        key_parts.append(_stable_group_key_tuple(group_key))
        return tuple(key_parts)

    def _value_sort_key(self, value: RuntimeValue, *, desc: bool) -> Tuple[int, int, "_ReversibleValue"]:
        # `None` 永远排在最后;其余尽量按数值排序(失败时回退为稳定字符串键).
        if value is None:
            return (1, 0, _ReversibleValue(_DECIMAL_ZERO, desc=False))
        dec = _to_decimal(value)
        if dec is not None:
            return (0, 0, _ReversibleValue(dec, desc=desc))
        return (0, 1, _ReversibleValue(_stable_sort_key(value), desc=desc))

    def _apply_rank_field(self, rows: List[Dict[str, CellValue]], spec: RankFieldSpec) -> None:
        partitions: Dict[Tuple[CellValue, ...], List[Dict[str, CellValue]]] = {}
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

    def __lt__(self, other: RuntimeValue) -> bool:
        if not isinstance(other, _ReversibleValue):
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
    def __eq__(self, other: RuntimeValue) -> bool:
        if not isinstance(other, _ReversibleValue):
            return False
        return bool(self.desc) == bool(other.desc) and self.value == other.value


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

    h = hashlib.sha256()
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


__all__ = ()
