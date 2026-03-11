from decimal import Decimal

import pytest

from scalim.execution import derived_outputs as mod
from scalim.sinks.sink_base import BaseRowSink


class _CollectingRowSink(BaseRowSink):
    def __init__(self) -> None:
        self.rows = []
        self.closed = False

    def write_row(self, row) -> None:  # type: ignore[no-untyped-def]
        self.rows.append(dict(row))

    def close(self) -> None:
        self.closed = True


class _DummyMetricState(mod._MetricState):  # noqa: SLF001
    def accumulate(self, row) -> None:  # type: ignore[no-untyped-def]
        return super(_DummyMetricState, self).accumulate(row)

    def finalize(self):  # type: ignore[no-untyped-def]
        return super(_DummyMetricState, self).finalize()


def test_metric_state_contract_and_stable_sort_key_variants() -> None:
    dummy = _DummyMetricState()
    with pytest.raises(NotImplementedError):
        dummy.accumulate({"x": 1})
    with pytest.raises(NotImplementedError):
        _ = dummy.finalize()

    # `_stable_sort_key` 的分支覆盖: `None`/`bool`/`Decimal`/任意对象
    assert mod._stable_sort_key(None) == "none"  # noqa: SLF001
    assert mod._stable_sort_key(True) == "bool:1"  # noqa: SLF001
    assert mod._stable_sort_key(Decimal("12.30")) == "num:12.30"  # noqa: SLF001
    obj = object()
    assert mod._stable_sort_key(obj).startswith(type(obj).__name__ + ":")  # noqa: SLF001


def test_metric_state_from_spec_error_branches_and_min_max_sum_metrics() -> None:
    assert mod._to_decimal(None) is None  # noqa: SLF001
    assert mod._to_decimal("") is None  # noqa: SLF001
    assert mod._to_decimal(True) == Decimal("1")  # noqa: SLF001
    assert mod._to_decimal(2) == Decimal("2")  # noqa: SLF001
    assert mod._to_decimal(0.1) == Decimal("0.1")  # noqa: SLF001
    assert mod._to_decimal("1.50") == Decimal("1.50")  # noqa: SLF001
    assert mod._to_decimal(Decimal("2.5")) == Decimal("2.5")  # noqa: SLF001
    assert mod._to_decimal("oops") is None  # noqa: SLF001
    assert mod._to_decimal(Decimal("NaN")) is None  # noqa: SLF001

    with pytest.raises(ValueError, match="count_true requires field_id"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_true"))  # noqa: SLF001
    count_true = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_true", field_id="flag"))  # noqa: SLF001
    count_true.accumulate({"flag": True})
    count_true.accumulate({"flag": False})
    assert count_true.finalize() == 1

    with pytest.raises(ValueError, match="sum requires field_id"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="sum"))  # noqa: SLF001
    sum_metric = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="sum", field_id="v"))  # noqa: SLF001
    sum_metric.accumulate({"v": None})
    sum_metric.accumulate({"v": "oops"})
    sum_metric.accumulate({"v": "1.5"})
    sum_metric.accumulate({"v": 0.1})
    sum_metric.accumulate({"v": 0.2})
    sum_metric.accumulate({"v": Decimal("2.2")})
    assert sum_metric.finalize() == Decimal("4.0")

    with pytest.raises(ValueError, match="min requires field_id"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="min"))  # noqa: SLF001
    assert mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="min", field_id="v")).__class__.__name__ == "_MinMetric"  # noqa: SLF001

    with pytest.raises(ValueError, match="max requires field_id"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="max"))  # noqa: SLF001
    assert mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="max", field_id="v")).__class__.__name__ == "_MaxMetric"  # noqa: SLF001

    with pytest.raises(ValueError, match="Unsupported aggregation op"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="avg", field_id="v"))  # noqa: SLF001


def test_min_max_metrics_finalize_branches() -> None:
    min_metric = mod._MinMetric("v")  # noqa: SLF001
    assert min_metric.finalize() is None
    min_metric.accumulate({"v": None})
    min_metric.accumulate({"v": "b"})
    min_metric.accumulate({"v": "a"})
    assert min_metric.finalize() == "a"

    max_metric = mod._MaxMetric("v")  # noqa: SLF001
    assert max_metric.finalize() is None
    max_metric.accumulate({"v": None})
    max_metric.accumulate({"v": "a"})
    max_metric.accumulate({"v": "b"})
    assert max_metric.finalize() == "b"

    min_metric_num = mod._MinMetric("v")  # noqa: SLF001
    min_metric_num.accumulate({"v": Decimal("0.5")})
    min_metric_num.accumulate({"v": 1.25})
    assert min_metric_num.finalize() == Decimal("0.5")

    max_metric_num = mod._MaxMetric("v")  # noqa: SLF001
    max_metric_num.accumulate({"v": Decimal("0.5")})
    max_metric_num.accumulate({"v": Decimal("9.5")})
    assert max_metric_num.finalize() == Decimal("9.5")


def test_group_by_aggregator_validation_and_ranked_finalize_branches() -> None:
    with pytest.raises(ValueError, match="group_by cannot be empty"):
        _ = mod.GroupByAggregator(group_by=(), metrics=(mod.AggMetricSpec(out_field_id="c", op="count"),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="metrics cannot be empty"):
        _ = mod.GroupByAggregator(group_by=("g",), metrics=())  # type: ignore[arg-type]

    agg = mod.RankedGroupByAggregator(
        group_by=("g",),
        metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),),
        rank_by="g",
        top_k=1,
    )
    assert agg.required_fields() == ("g",)

    obj = object()
    agg.accumulate({"g": None})
    agg.accumulate({"g": obj})
    agg.accumulate({"g": "app"})
    rows = agg.finalize_rows()
    assert len(rows) == 1
    assert rows[0]["rank"] == 1


def test_aggregating_row_sink_close_and_closed_guards() -> None:
    out = _CollectingRowSink()
    agg = mod.GroupByAggregator(
        group_by=("g",),
        metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),),
    )
    sink = mod.AggregatingRowSink(aggregator=agg, out_sink=out)
    assert sink.aggregator is agg
    assert sink.out_sink is out

    sink.write_row({"g": "a"})
    sink.write_row({"g": "a"})
    sink.close()
    sink.close()

    assert out.closed is True
    assert out.rows[0]["cnt"] == 2

    with pytest.raises(RuntimeError, match="AggregatingRowSink is closed"):
        sink.write_row({"g": "b"})
