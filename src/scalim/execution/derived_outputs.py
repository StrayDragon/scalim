from __future__ import absolute_import

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union, cast

from ..sinks.sink_base import BaseRowSink, IRowSink
from ..typedefs import FieldValue, RowData
from ..vendor.compact.typing_extensionsx import override


class AggregationKeyLimitExceededError(RuntimeError):
    group_count: int
    max_groups: int

    def __init__(self, *, group_count: int, max_groups: int) -> None:
        super(AggregationKeyLimitExceededError, self).__init__(
            "Group-by key cardinality exceeded: group_count={} > max_groups={}".format(int(group_count), int(max_groups))
        )
        self.group_count = int(group_count)
        self.max_groups = int(max_groups)


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


@dataclass(frozen=True)
class AggMetricSpec:
    """聚合指标定义(内置)."""

    out_field_id: str
    op: str
    field_id: Optional[str] = None


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


def _metric_state_from_spec(spec: AggMetricSpec) -> _MetricState:
    op = str(spec.op).lower()
    if op == "count":
        return _CountMetric(spec.field_id)
    if op == "count_true":
        if not spec.field_id:
            msg = "count_true requires field_id"
            raise ValueError(msg)
        return _CountTrueMetric(spec.field_id)
    if op == "sum":
        if not spec.field_id:
            msg = "sum requires field_id"
            raise ValueError(msg)
        return _SumMetric(spec.field_id)
    if op == "min":
        if not spec.field_id:
            msg = "min requires field_id"
            raise ValueError(msg)
        return _MinMetric(spec.field_id)
    if op == "max":
        if not spec.field_id:
            msg = "max requires field_id"
            raise ValueError(msg)
        return _MaxMetric(spec.field_id)
    msg = "Unsupported aggregation op: {!r}".format(spec.op)
    raise ValueError(msg)


class GroupByAggregator(IRowAggregator):
    _group_by: Tuple[str, ...]
    _metrics: Tuple[AggMetricSpec, ...]
    _states: Dict[Tuple[FieldValue, ...], Tuple[_MetricState, ...]]
    _max_groups: int

    def __init__(
        self,
        *,
        group_by: Sequence[str],
        metrics: Sequence[AggMetricSpec],
        max_groups: int = 0,
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

    @override
    def required_fields(self) -> Tuple[str, ...]:
        required: List[str] = list(self._group_by)
        for m in self._metrics:
            if m.field_id:
                required.append(str(m.field_id))
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
        key = tuple(row.get(fid) for fid in self._group_by)
        state = self._states.get(key)
        if state is None:
            if self._max_groups and len(self._states) >= self._max_groups:
                raise AggregationKeyLimitExceededError(group_count=len(self._states) + 1, max_groups=self._max_groups)
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
            out: Dict[str, FieldValue] = {}
            for idx, fid in enumerate(self._group_by):
                out[fid] = key[idx] if idx < len(key) else None
            for metric_spec, metric_state in zip(self._metrics, state):
                out[str(metric_spec.out_field_id)] = metric_state.finalize()
            rows.append(out)
        return rows


class RankedGroupByAggregator(IRowAggregator):
    """`GroupBy` + `finalize` 阶段排序/排名.

    说明:
    - 排名仅在 `finalize` 阶段执行(单线程),用于保持结果确定性.
    - 平局时(`tie-break`)使用 `group_by` 键的稳定字符串键,避免对拍误报.
    """

    _base: GroupByAggregator
    _group_by: Tuple[str, ...]
    _rank_by: str
    _rank_field_id: str
    _order: str
    _top_k: int

    def __init__(
        self,
        *,
        group_by: Sequence[str],
        metrics: Sequence[AggMetricSpec],
        rank_by: str,
        rank_field_id: str = "rank",
        order: str = "desc",
        top_k: int = 0,
        max_groups: int = 0,
    ) -> None:
        self._group_by = tuple(str(item) for item in group_by)
        self._rank_by = str(rank_by)
        self._rank_field_id = str(rank_field_id)
        self._order = str(order or "desc").lower()
        self._top_k = int(top_k) if top_k else 0
        self._base = GroupByAggregator(group_by=self._group_by, metrics=metrics, max_groups=max_groups)

    @override
    def required_fields(self) -> Tuple[str, ...]:
        return self._base.required_fields()

    @override
    def accumulate(self, row: RowData) -> None:
        self._base.accumulate(row)

    @override
    def finalize_rows(self) -> List[RowData]:
        # 将 `base` 输出显式转为可变 `dict`,以便追加 `rank` 字段.
        rows: List[Dict[str, FieldValue]] = [dict(r) for r in self._base.finalize_rows()]

        def _rank_value_key(v: object) -> Tuple[int, Decimal, str]:
            # `None` 永远排在最后;其余尽量按数值排序(失败时回退为稳定字符串键).
            if v is None:
                return (1, _DECIMAL_ZERO, "")
            dec = _to_decimal(cast("NonNullFieldValue", v))
            if dec is not None:
                return (0, dec, "")
            return (0, _DECIMAL_ZERO, _stable_sort_key(v))

        def _row_sort_key(r: RowData) -> Tuple[int, Decimal, str, str]:
            group_key = tuple(r.get(fid) for fid in self._group_by)
            is_none, num_dec, s = _rank_value_key(r.get(self._rank_by))
            if self._order != "asc":
                num_dec = -num_dec
            return (is_none, num_dec, s, _stable_group_key_tuple(group_key))

        rows.sort(key=_row_sort_key)

        if self._top_k > 0:
            rows = rows[: int(self._top_k)]

        for idx, row in enumerate(rows):
            row[self._rank_field_id] = int(idx) + 1
        return list(rows)


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
