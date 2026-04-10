"""集成测试 - 使用真实 demo 数据进行端到端测试.

这些测试使用 examples/demo_report_ir 中的真实数据,
验证整个数据处理流程的正确性.
"""

import pytest
from typing import List, Optional

from scalim.execution import ScalimEngine

try:
    from scalim_misc.example_report_ir import build_order_report_model, build_order_report_runtime_bindings
except Exception as exc:
    pytest.skip("demo integration dependencies unavailable in this environment: {}".format(exc), allow_module_level=True)
from scalim.planning import PlanBuilder
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.typedefs import RowData

from tests.support.testing_utils import ColumnListSink, ListSink, StreamingListSink


pytestmark = pytest.mark.slow


# region Fixtures


@pytest.fixture(scope="module")
def demo_model():
    """加载 demo 模型 (模块级别缓存)"""

    return build_order_report_model()


@pytest.fixture(scope="module")
def demo_runtime_bindings() -> "RuntimeBindings":
    return build_order_report_runtime_bindings()


@pytest.fixture
def plan_builder(demo_model):
    """创建 PlanBuilder"""
    return PlanBuilder(demo_model)


def _get_main_rows(
    demo_model,
    runtime_bindings: "RuntimeBindings",
    limit: Optional[int] = None,
    order_ids: Optional[List[int]] = None,
) -> List[RowData]:
    main_source = demo_model.main_source
    if main_source is None:
        return []
    params = dict(main_source.params or {})
    if order_ids is not None:
        params["order_ids"] = order_ids
    if params:
        rows = list(runtime_bindings.require_main_source_loader(main_source.source_id)(**params))
    else:
        rows = list(runtime_bindings.require_main_source_loader(main_source.source_id)())
    if limit is not None:
        return rows[:limit]
    return rows


# endregion


# region 测试: PlanBuilder 真实场景


class TestPlanBuilderRealData:
    """PlanBuilder 真实数据测试"""

    def test_build_simple_targets(self, plan_builder) -> None:
        """测试简单目标字段构建"""
        plan = plan_builder.build(targets=["order_id", "amount"])

        assert "order_id" in plan.target_fields
        assert "amount" in plan.target_fields
        assert len(plan.field_order) >= 2

    def test_build_with_derived_field(self, plan_builder) -> None:
        """测试包含派生字段的构建"""
        plan = plan_builder.build(targets=["order_id", "profit"])

        # profit 依赖 amount 和 cost
        assert "profit" in plan.target_fields
        assert "amount" in plan.field_order
        assert "cost" in plan.field_order

        # 验证拓扑顺序
        profit_idx = plan.field_order.index("profit")
        amount_idx = plan.field_order.index("amount")
        cost_idx = plan.field_order.index("cost")
        assert profit_idx > amount_idx
        assert profit_idx > cost_idx

    def test_build_with_relation_field(self, plan_builder) -> None:
        """测试包含关联字段的构建"""
        plan = plan_builder.build(targets=["order_id", "customer_name"])

        # customer_name 依赖 customer_id
        assert "customer_name" in plan.target_fields
        assert "customer_id" in plan.field_order

        # 验证有关联 loader
        assert len(plan.ref_loader_sequence) >= 1

    def test_build_with_multi_level_relation(self, plan_builder) -> None:
        """测试多级关联字段构建"""
        plan = plan_builder.build(targets=["order_id", "country_name"])

        # country_name 通过 orders -> pays -> countries 关联
        assert "country_name" in plan.target_fields
        assert "pay_id" in plan.field_order
        # country_id 是中间路径的外键
        assert "country_id" in plan.field_order

    def test_build_with_multi_field_relation(self, plan_builder) -> None:
        """测试多字段关联 (复合主键) 构建"""
        plan = plan_builder.build(targets=["order_id", "mapping_name"])

        # mapping_name 依赖 region_id 和 institution_id
        assert "mapping_name" in plan.target_fields
        assert "region_id" in plan.field_order
        assert "institution_id" in plan.field_order

    def test_build_full_targets(self, plan_builder) -> None:
        """测试完整目标字段构建"""
        targets = ["order_id", "amount", "profit", "customer_name", "order_source", "country_name", "mapping_name", "order_type_name"]
        plan = plan_builder.build(targets=targets)

        assert set(plan.target_fields) == set(targets)
        assert plan.metadata.has_derived_fields is True
        assert plan.metadata.has_ref_fields is True


# endregion


# region 测试: IREngine 真实执行


class TestIREngineRealExecution:
    """IREngine 真实数据执行测试"""

    def test_execute_simple_fields(self, demo_model, demo_runtime_bindings) -> None:
        """测试简单字段执行"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "amount"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证数据正确性
        for row in results:
            assert "order_id" in row
            assert "amount" in row
            assert isinstance(row["order_id"], int)

    def test_execute_derived_field(self, demo_model, demo_runtime_bindings) -> None:
        """测试派生字段执行"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "amount", "cost", "profit"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证 profit = amount - cost (格式化为字符串)
        for row in results:
            amount = row["amount"] or 0
            cost = row["cost"] or 0
            expected_profit = f"{amount - cost:.2f}"
            assert row["profit"] == expected_profit

    def test_execute_relation_field(self, demo_model, demo_runtime_bindings) -> None:
        """测试关联字段执行"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "customer_name"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证客户名称格式
        for row in results:
            assert "customer_name" in row
            if row["customer_name"]:
                assert row["customer_name"].startswith("customer_")

    def test_execute_multi_level_relation(self, demo_model, demo_runtime_bindings) -> None:
        """测试多级关联执行"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "country_name"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证国家名称格式
        for row in results:
            assert "country_name" in row
            if row["country_name"]:
                assert row["country_name"].startswith("country_")

    def test_execute_multi_field_relation(self, demo_model, demo_runtime_bindings) -> None:
        """测试多字段关联执行"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "mapping_name"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证映射名称格式
        for row in results:
            assert "mapping_name" in row
            if row["mapping_name"]:
                assert row["mapping_name"].startswith("mapping_")

    def test_execute_with_transform(self, demo_model, demo_runtime_bindings) -> None:
        """测试字段转换执行"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "order_source"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证转换结果
        valid_sources = {"小程序", "线下", "其他"}
        for row in results:
            assert row["order_source"] in valid_sources

    def test_execute_with_preload_cache(self, demo_model, demo_runtime_bindings) -> None:
        """测试预加载缓存 (FR003)"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "order_type_name"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 5))

        assert len(results) == 5

        # 验证订单类型名称
        valid_types = {"普通订单", "VIP订单", "团购订单", "秒杀订单", "预售订单"}
        for row in results:
            if row["order_type_name"]:
                assert row["order_type_name"] in valid_types


# endregion


# region 测试: Sink 模式


class TestSinkModes:
    """不同 Sink 模式测试"""

    def test_normal_sink(self, demo_model, demo_runtime_bindings) -> None:
        """测试普通 Sink"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "profit"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=3)
        sink = ListSink()

        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 6), sink=sink)

        assert results == []  # 使用 sink 时返回空
        assert sink.closed is True
        assert len(sink.rows) == 6

    def test_streaming_sink(self, demo_model, demo_runtime_bindings) -> None:
        """测试流式 Sink"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "profit"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=3)
        sink = StreamingListSink()

        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 6), sink=sink)

        assert results == []
        assert sink.closed is True
        assert len(sink.rows) == 6

    def test_column_sink(self, demo_model, demo_runtime_bindings) -> None:
        """测试列式 Sink"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "profit"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=3)
        sink = ColumnListSink()

        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 6), sink=sink)

        assert results == []
        assert sink.closed is True
        assert "order_id" in sink.columns
        assert "profit" in sink.columns

    def test_sink_modes_consistency(self, demo_model, demo_runtime_bindings) -> None:
        """测试不同 Sink 模式结果一致性"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "profit", "customer_name"])
        main_rows = _get_main_rows(demo_model, demo_runtime_bindings, 5)

        # 普通模式
        engine1 = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=10)
        results1 = engine1.run(main_rows=main_rows)

        # 流式模式
        engine2 = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=10)
        streaming_sink = StreamingListSink()
        engine2.run(main_rows=main_rows, sink=streaming_sink)
        results2 = streaming_sink.rows

        # 列式模式
        engine3 = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=10)
        column_sink = ColumnListSink()
        engine3.run(main_rows=main_rows, sink=column_sink)

        # 验证结果一致
        assert len(results1) == len(results2) == 5

        for i in range(5):
            r1 = results1[i]
            r2 = results2[i]

            assert r1["order_id"] == r2["order_id"]
            assert r1["profit"] == r2["profit"]
            assert r1["customer_name"] == r2["customer_name"]


# endregion


# region 测试: 批处理


class TestBatchProcessing:
    """批处理测试"""

    def test_different_batch_sizes(self, demo_model, demo_runtime_bindings) -> None:
        """测试不同批次大小"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "amount"])
        main_rows = _get_main_rows(demo_model, demo_runtime_bindings, 10)

        # 小批次
        engine1 = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=2)
        results1 = engine1.run(main_rows=main_rows)

        # 大批次
        engine2 = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=100)
        results2 = engine2.run(main_rows=main_rows)

        # 结果应该一致
        assert len(results1) == len(results2) == 10

        for r1, r2 in zip(results1, results2):
            assert r1["order_id"] == r2["order_id"]
            assert r1["amount"] == r2["amount"]

    def test_batch_size_one(self, demo_model, demo_runtime_bindings) -> None:
        """测试批次大小为 1"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id", "profit"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=1)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, 3))

        assert len(results) == 3

    def test_empty_input(self, demo_model, demo_runtime_bindings) -> None:
        """测试空输入"""
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id"])

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=10)
        results = engine.run(main_rows=[])

        assert results == []


# endregion


# region 测试: 完整流程


class TestFullPipeline:
    """完整流程测试"""

    def test_full_report_generation(self, demo_model, demo_runtime_bindings) -> None:
        """测试完整报表生成"""
        targets = ["order_id", "amount", "profit", "customer_name", "order_source", "country_name", "mapping_name", "order_type_name"]

        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=targets)

        engine = ScalimEngine(demand=demo_model, plan=plan, runtime_bindings=demo_runtime_bindings, batch_size=5)
        results = engine.run(main_rows=_get_main_rows(demo_model, demo_runtime_bindings, order_ids=list(range(15))))

        assert len(results) == 15

        # 验证所有字段都存在
        for row in results:
            for target in targets:
                assert target in row

    def test_pruning_effectiveness(self, demo_model) -> None:
        """测试剪枝效果"""
        # 只请求少量字段
        builder = PlanBuilder(demo_model)
        plan = builder.build(targets=["order_id"])

        # 应该剪枝掉大部分字段
        assert plan.metadata.pruned_fields > 0

        # 只有 order_id 在目标中
        assert plan.target_fields == ["order_id"]


# endregion
