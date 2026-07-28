from decimal import Decimal

import pytest

from scalim.execution import derived_outputs as mod
from scalim.sinks import BaseRowSink


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

    with pytest.raises(ValueError, match="count_distinct does not allow both field_id and field_ids"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_distinct", field_id="a", field_ids=("b",)))  # noqa: SLF001
    with pytest.raises(ValueError, match="count_distinct requires field_id or field_ids"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_distinct"))  # noqa: SLF001
    with pytest.raises(ValueError, match=r"count_distinct requires field_id\(s\)"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_distinct", field_ids=("",)))  # noqa: SLF001

    with pytest.raises(ValueError, match="count_true_gte requires field_id"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_true_gte", threshold=2))  # noqa: SLF001
    with pytest.raises(ValueError, match="count_true_gte requires threshold"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_true_gte", field_id="v"))  # noqa: SLF001
    with pytest.raises(ValueError, match="count_true_gte requires numeric threshold"):
        _ = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_true_gte", field_id="v", threshold="oops"))  # noqa: SLF001

    gte = mod._metric_state_from_spec(mod.AggMetricSpec(out_field_id="x", op="count_true_gte", field_id="v", threshold=2))  # noqa: SLF001
    gte.accumulate({"v": None})
    gte.accumulate({"v": "oops"})
    gte.accumulate({"v": 2})
    assert gte.finalize() == 1


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
        rank_fields=(
            mod.RankFieldSpec(
                out_field_id="rank",
                kind="dense_rank",
                by="cnt",
                order="desc",
                top_k=1,
                top_k_mode="rank",
            ),
        ),
        post_fields=(
            mod.PostFieldSpec(
                out_field_id="score",
                kind="test",
                dependencies=("rank",),
                fingerprint="score=rank*10",
                calculator=lambda row: int(row.get("rank") or 0) * 10,
            ),
        ),
    )
    assert agg.required_fields() == ("g",)

    agg.accumulate({"g": "a"})
    agg.accumulate({"g": "a"})
    agg.accumulate({"g": "b"})
    agg.accumulate({"g": "b"})
    agg.accumulate({"g": "c"})
    rows = agg.finalize_rows()
    # top_k_mode=rank expands ties (a/b both cnt=2)
    assert rows == [
        {"g": "a", "cnt": 2, "rank": 1, "score": 10},
        {"g": "b", "cnt": 2, "rank": 1, "score": 10},
    ]
    assert agg.diagnostics().meta["group_count"] == 3


def test_ranked_group_by_aggregator_partition_and_top_k_rows_mode() -> None:
    agg = mod.RankedGroupByAggregator(
        group_by=("region", "g"),
        metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),),
        rank_fields=(
            mod.RankFieldSpec(
                out_field_id="rank",
                kind="rank",
                by="cnt",
                partition_by=("region",),
                order="desc",
                order_by=("cnt", "g"),
                top_k=1,
                top_k_mode="rows",
            ),
        ),
    )

    agg.accumulate({"region": "r1", "g": "a"})
    agg.accumulate({"region": "r1", "g": "a"})
    agg.accumulate({"region": "r1", "g": "b"})

    agg.accumulate({"region": "r2", "g": "a"})
    agg.accumulate({"region": "r2", "g": "b"})

    rows = agg.finalize_rows()
    # r1: cnt(a)=2, cnt(b)=1 -> keep a
    # r2: cnt(a)=1, cnt(b)=1 -> order_by desc (g: b > a) -> keep b
    assert rows == [
        {"region": "r1", "g": "a", "cnt": 2, "rank": 1},
        {"region": "r2", "g": "b", "cnt": 1, "rank": 1},
    ]


def test_ranked_group_by_aggregator_finalize_empty_returns_empty_list() -> None:
    agg = mod.RankedGroupByAggregator(group_by=("g",), metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),))
    assert agg.finalize_rows() == []


def test_ranked_group_by_aggregator_without_rank_fields_skips_primary_rank() -> None:
    agg = mod.RankedGroupByAggregator(group_by=("g",), metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),))
    agg.accumulate({"g": "a"})
    assert agg.finalize_rows() == [{"g": "a", "cnt": 1}]


def test_ranked_group_by_aggregator_value_sort_key_none_branch() -> None:
    agg = mod.RankedGroupByAggregator(group_by=("g",), metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),))
    key = agg._value_sort_key(None, desc=False)  # noqa: SLF001
    assert key[0] == 1


def test_reversible_value_hash_and_mixed_type_lt_fallback_branch() -> None:
    left = mod._ReversibleValue(Decimal("1"), desc=False)  # noqa: SLF001
    right = mod._ReversibleValue("x", desc=False)  # noqa: SLF001
    assert isinstance(hash(left), int)
    assert (left < right) in (True, False)


def test_reversible_value_rich_comparison_rejects_non_reversible_other() -> None:
    left = mod._ReversibleValue(Decimal("1"), desc=False)  # noqa: SLF001
    assert left.__lt__(1) is NotImplemented
    assert left.__eq__("x") is False


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


def test_count_distinct_single_and_composite_and_missing_value_semantics() -> None:
    agg = mod.GroupByAggregator(
        group_by=("g",),
        metrics=(
            mod.AggMetricSpec(out_field_id="u", op="count_distinct", field_id="user_id"),
            mod.AggMetricSpec(out_field_id="c", op="count_distinct", field_ids=("cs_id", "user_id")),
        ),
    )
    assert agg.required_fields() == ("g", "user_id", "cs_id")

    # duplicates
    agg.accumulate({"g": "x", "cs_id": 1, "user_id": "u1"})
    agg.accumulate({"g": "x", "cs_id": 1, "user_id": "u1"})
    agg.accumulate({"g": "x", "cs_id": 1, "user_id": "u2"})

    # missing values: any None in the key is ignored (SQL COUNT(DISTINCT) NULL semantics)
    agg.accumulate({"g": "x", "cs_id": 1, "user_id": None})
    agg.accumulate({"g": "x", "cs_id": None, "user_id": "u3"})

    rows = agg.finalize_rows()
    assert rows == [{"g": "x", "u": 3, "c": 2}]

    # 诊断: `count_distinct` 的 `distinct_keys_total` / `distinct_keys_max_per_group` 统计(无截断事件).
    diag = agg.diagnostics()
    assert diag.meta["group_count"] == 1
    assert diag.meta["metric.u.distinct_keys_total"] == 3
    assert diag.meta["metric.u.distinct_keys_max_per_group"] == 3
    assert diag.meta["metric.c.distinct_keys_total"] == 2
    assert diag.audit_events == []


def test_group_by_diagnostics_skips_unexpected_distinct_metric_state() -> None:
    agg = mod.GroupByAggregator(
        group_by=("g",),
        metrics=(mod.AggMetricSpec(out_field_id="u", op="count_distinct", field_id="user_id"),),
    )
    agg.accumulate({"g": "x", "user_id": "u1"})

    # 防御性覆盖: 若内部状态不符合预期类型, diagnostics 应跳过并继续.
    agg._states[("x",)] = (_DummyMetricState(),)  # noqa: SLF001
    diag = agg.diagnostics()
    assert diag.meta["group_count"] == 1
    assert diag.meta["metric.u.distinct_keys_total"] == 0


def test_count_true_gte_via_manual_stage_feed() -> None:
    # Migration alternative to removed TwoStageGroupByAggregator: stage1 finalize → stage2 accumulate.
    stage1 = mod.GroupByAggregator(
        group_by=("cs_id", "user_id"),
        metrics=(mod.AggMetricSpec(out_field_id="pay_order_cnt", op="count", field_id="order_id"),),
    )
    stage2 = mod.GroupByAggregator(
        group_by=("cs_id",),
        metrics=(mod.AggMetricSpec(out_field_id="repeat_paid_users", op="count_true_gte", field_id="pay_order_cnt", threshold=2),),
    )
    assert stage1.required_fields() == ("cs_id", "user_id", "order_id")

    rows = [
        {"order_id": 1, "cs_id": 1, "user_id": "u1"},
        {"order_id": 2, "cs_id": 1, "user_id": "u1"},
        {"order_id": 3, "cs_id": 1, "user_id": "u2"},
        {"order_id": 4, "cs_id": 2, "user_id": "u3"},
        {"order_id": 5, "cs_id": 2, "user_id": "u3"},
        {"order_id": 6, "cs_id": 2, "user_id": "u3"},
    ]
    for r in rows:
        stage1.accumulate(r)

    for mid in stage1.finalize_rows():
        stage2.accumulate(mid)

    out = stage2.finalize_rows()
    assert out == [
        {"cs_id": 1, "repeat_paid_users": 1},
        {"cs_id": 2, "repeat_paid_users": 1},
    ]
    assert stage1.diagnostics().meta["group_count"] == 3
    assert stage2.diagnostics().meta["group_count"] == 2


def test_group_by_aggregator_key_normalization_merges_semantically_equal_keys() -> None:
    agg = mod.GroupByAggregator(
        group_by=("g",),
        metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),),
        key_normalization="auto_str",  # type: ignore[arg-type]
    )
    agg.accumulate({"g": 1})
    agg.accumulate({"g": "1"})
    agg.accumulate({"g": None})
    assert agg.finalize_rows() == [{"g": None, "cnt": 1}, {"g": "1", "cnt": 2}]


def test_group_by_aggregator_key_normalization_fail_fast_message_is_safe() -> None:
    agg = mod.GroupByAggregator(
        group_by=("g",),
        metrics=(mod.AggMetricSpec(out_field_id="cnt", op="count"),),
        key_normalization="auto_str",  # type: ignore[arg-type]
    )
    raw = object()
    with pytest.raises(ValueError) as excinfo:
        agg.accumulate({"g": raw})
    assert "key_normalization failed for group_by key field" in str(excinfo.value)
    assert "type=object" in str(excinfo.value)
    assert "0x" not in str(excinfo.value)
