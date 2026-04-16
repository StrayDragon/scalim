import pytest

from scalim.execution.engine import ScalimEngine
from scalim.planning import PlanBuilder

from tests.cases.minimal_ir import build_minimal_ir_case
from tests.support.testing_utils import ColumnListSink, ListSink, StreamingListSink


@pytest.fixture(scope="module")
def minimal_case():
    return build_minimal_ir_case()


@pytest.fixture(scope="module")
def minimal_demand(minimal_case):
    return minimal_case.demand


def test_plan_builder_builds_and_prunes(minimal_demand) -> None:
    plan = PlanBuilder(minimal_demand).build(targets=["order_id"])
    assert plan.target_fields == ["order_id"]
    assert plan.metadata.pruned_fields > 0


def test_engine_computes_derived_and_relations(minimal_case) -> None:
    demand = minimal_case.demand
    plan = PlanBuilder(demand).build(
        targets=["order_id", "profit", "customer_name", "country_name", "mapping_name", "order_type_name", "order_source"]
    )
    assert any(source.source_id == "order_types" and source.is_preload_forever() for source in plan.preload_sources)
    results = ScalimEngine(demand=demand, plan=plan, runtime_bindings=minimal_case.runtime_bindings, batch_size=10).run(
        main_rows=minimal_case.main_rows()
    )

    assert len(results) == 2
    assert results[0]["order_id"] == 1
    assert results[0]["profit"] == "60.00"
    assert results[0]["customer_name"] == "customer_1"
    assert results[0]["country_name"] == "country_cn"
    assert results[0]["mapping_name"] == "mapping_1_10"
    assert results[0]["order_type_name"] == "normal"
    assert results[0]["order_source"] == "app"


def test_sink_modes_consistent(minimal_case) -> None:
    demand = minimal_case.demand
    plan = PlanBuilder(demand).build(targets=["order_id", "profit", "customer_name"])
    main_rows = minimal_case.main_rows()

    engine_plain = ScalimEngine(demand=demand, plan=plan, runtime_bindings=minimal_case.runtime_bindings, batch_size=10)
    results_plain = engine_plain.run(main_rows=main_rows)

    engine_streaming = ScalimEngine(demand=demand, plan=plan, runtime_bindings=minimal_case.runtime_bindings, batch_size=10)
    streaming_sink = StreamingListSink()
    results_streaming = engine_streaming.run(main_rows=main_rows, sink=streaming_sink)
    assert results_streaming == []

    engine_column = ScalimEngine(demand=demand, plan=plan, runtime_bindings=minimal_case.runtime_bindings, batch_size=10)
    column_sink = ColumnListSink()
    results_column = engine_column.run(main_rows=main_rows, sink=column_sink)
    assert results_column == []

    rows_streaming = streaming_sink.rows
    rows_column = column_sink.to_rows()

    assert len(results_plain) == len(rows_streaming) == len(rows_column) == 2
    for idx in range(2):
        assert results_plain[idx]["order_id"] == rows_streaming[idx]["order_id"] == rows_column[idx]["order_id"]
        assert results_plain[idx]["profit"] == rows_streaming[idx]["profit"] == rows_column[idx]["profit"]
        assert results_plain[idx]["customer_name"] == rows_streaming[idx]["customer_name"] == rows_column[idx]["customer_name"]


def test_sinks_close(minimal_case) -> None:
    demand = minimal_case.demand
    plan = PlanBuilder(demand).build(targets=["order_id", "profit"])
    main_rows = minimal_case.main_rows()

    sink = ListSink()
    results = ScalimEngine(demand=demand, plan=plan, runtime_bindings=minimal_case.runtime_bindings, batch_size=10).run(
        main_rows=main_rows, sink=sink
    )
    assert results == []
    assert sink.closed is True
    assert len(sink.rows) == 2
