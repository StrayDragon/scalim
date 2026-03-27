"""IREngine 和 BatchContext 行为测试.

测试执行引擎的输入输出契约,不测试内部实现细节.
"""

import pytest
from typing import Any, Dict, List, Optional, Set

from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import DerivedFieldIr, FieldIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr
from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.execution.context import BatchContext
from scalim.sinks import InMemoryRowSink


# region Mock Data Loaders


class MockDataLoader:
    """测试用数据加载器"""

    def __init__(self) -> None:
        # 订单数据
        self.orders: Dict[int, Dict[str, Any]] = {
            0: {"order_id": 0, "amount": 100, "cost": 60, "customer_id": 100},
            1: {"order_id": 1, "amount": 200, "cost": 120, "customer_id": 101},
            2: {"order_id": 2, "amount": 300, "cost": 180, "customer_id": 102},
        }

        # 客户数据
        self.customers: Dict[int, Dict[str, Any]] = {
            100: {"customer_id": 100, "customer_name": "Alice"},
            101: {"customer_id": 101, "customer_name": "Bob"},
            102: {"customer_id": 102, "customer_name": "Charlie"},
        }

        # 调用计数
        self.call_count: Dict[str, int] = {}

    def get_orders(self, order_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        self.call_count["orders"] = self.call_count.get("orders", 0) + 1
        rows = list(self.orders.values())
        if order_ids:
            return [row for row in rows if row.get("order_id") in order_ids]
        return rows

    def get_customers(self, customer_ids_set: Optional[Set[int]] = None) -> Dict[int, Dict[str, Any]]:
        self.call_count["customers"] = self.call_count.get("customers", 0) + 1
        if customer_ids_set:
            return {k: v for k, v in self.customers.items() if k in customer_ids_set}
        return self.customers


# endregion


# region Fixtures


@pytest.fixture
def mock_loader() -> MockDataLoader:
    """创建 Mock 数据加载器"""
    return MockDataLoader()


@pytest.fixture
def simple_model(mock_loader: MockDataLoader) -> DemandIr:
    """简单模型: 单数据源,无关联"""
    orders_source = MainSourceIr(
        source_id="orders",
        loader=mock_loader.get_orders,
    )

    fields = [
        FieldIr(
            field_id="order_id",
            name="订单ID",
            source=orders_source,
            is_primary=True,
        ),
        FieldIr(
            field_id="amount",
            name="金额",
            source=orders_source,
        ),
    ]

    return DemandIr.from_irs(
        sources=[],
        fields=fields,
        main_source=orders_source,
    )


@pytest.fixture
def derived_model(mock_loader: MockDataLoader) -> DemandIr:
    """派生字段模型"""
    orders_source = MainSourceIr(
        source_id="orders",
        loader=mock_loader.get_orders,
    )

    fields = [
        FieldIr(
            field_id="order_id",
            name="订单ID",
            source=orders_source,
            is_primary=True,
        ),
        FieldIr(
            field_id="amount",
            name="金额",
            source=orders_source,
        ),
        FieldIr(
            field_id="cost",
            name="成本",
            source=orders_source,
        ),
        DerivedFieldIr(
            field_id="profit",
            name="利润",
            dependencies=("amount", "cost"),
            calculator=lambda amount, cost: (amount or 0) - (cost or 0),
        ),
    ]

    return DemandIr.from_irs(
        sources=[],
        fields=fields,
        main_source=orders_source,
    )


@pytest.fixture
def relation_model(mock_loader: MockDataLoader) -> DemandIr:
    """关联字段模型"""
    customers_loader = LoaderIr(
        callable=mock_loader.get_customers,
        bindings={
            "customer_id": BindingIr(
                key_field="customer_id",
                params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys}),
            ),
        },
    )

    orders_source = MainSourceIr(
        source_id="orders",
        loader=mock_loader.get_orders,
    )

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=customers_loader,
    )

    # 关联关系
    orders_to_customers = orders_source["customer_id"].join(customers_source["customer_id"])

    fields = [
        FieldIr(
            field_id="order_id",
            name="订单ID",
            source=orders_source,
            is_primary=True,
        ),
        FieldIr(
            field_id="amount",
            name="金额",
            source=orders_source,
        ),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source=customers_source,
            data_key="customer_name",
            relation=orders_to_customers,
        ),
    ]

    return DemandIr.from_irs(
        sources=[customers_source],
        fields=fields,
        main_source=orders_source,
    )


# endregion


# region Fixture: 派生字段链模型 (A -> B -> C)


@pytest.fixture
def chained_derived_model(mock_loader: MockDataLoader) -> DemandIr:
    """派生字段链模型: C 依赖 B, B 依赖 A (amount)

    用于测试 _compute_required_fields 是否正确收集完整依赖闭包
    """
    orders_source = MainSourceIr(
        source_id="orders",
        loader=mock_loader.get_orders,
    )

    fields = [
        FieldIr(
            field_id="order_id",
            name="订单ID",
            source=orders_source,
            is_primary=True,
        ),
        FieldIr(
            field_id="amount",
            name="金额",
            source=orders_source,
        ),
        DerivedFieldIr(
            field_id="b_double_amount",
            name="双倍金额",
            dependencies=("amount",),
            calculator=lambda amount: (amount or 0) * 2,
        ),
        DerivedFieldIr(
            field_id="c_triple_b",
            name="三倍B",
            dependencies=("b_double_amount",),
            calculator=lambda b_double_amount: (b_double_amount or 0) * 3,
        ),
    ]

    return DemandIr.from_irs(
        sources=[],
        fields=fields,
        main_source=orders_source,
    )


# endregion


# region 测试: BatchContext


def _build_ctx_with_amounts() -> BatchContext:
    ctx: BatchContext = BatchContext()
    ctx.set_field_value("amount", 1, 100)
    ctx.set_field_value("amount", 2, 200)
    return ctx


class TestBatchContext:
    """BatchContext 行为测试"""

    @pytest.mark.parametrize(
        "row_id,expected",
        [
            (1, 100),
            (2, 200),
            (3, None),
        ],
        ids=["row-1", "row-2", "row-missing"],
    )
    def test_get_field_value(self, row_id: int, expected: Optional[int]) -> None:
        """测试字段值存取"""
        ctx = _build_ctx_with_amounts()
        assert ctx.get_field_value("amount", row_id) == expected

    def test_get_with_default(self) -> None:
        """测试带默认值获取"""
        ctx: BatchContext = BatchContext()

        assert ctx.get_field_value("nonexistent", 1, default="default") == "default"

    def test_has_field(self) -> None:
        """测试字段存在检查"""
        ctx: BatchContext = BatchContext()

        assert ctx.has_field("amount") is False

        ctx.set_field_value("amount", 1, 100)

        assert ctx.has_field("amount") is True

    def test_delete_field(self) -> None:
        """测试字段删除"""
        ctx = _build_ctx_with_amounts()
        ctx.delete_field("amount")

        assert ctx.has_field("amount") is False
        assert ctx.get_field_value("amount", 1) is None

    def test_required_fields_filtering(self) -> None:
        """测试 required_fields 过滤"""
        ctx: BatchContext = BatchContext(required_fields={"amount"})

        # 只有 amount 会被存储
        ctx.set_field_value("amount", 1, 100)
        ctx.set_field_value("cost", 1, 60)  # 应该被忽略

        assert ctx.get_field_value("amount", 1) == 100
        assert ctx.get_field_value("cost", 1) is None

    def test_delete_row_from_field(self) -> None:
        """测试从字段中删除特定行"""
        ctx = _build_ctx_with_amounts()
        ctx.delete_row_from_field("amount", 1)

        assert ctx.get_field_value("amount", 1) is None
        assert ctx.get_field_value("amount", 2) == 200

    def test_delete_row_from_all_fields(self) -> None:
        """测试从所有字段中删除特定行"""
        ctx: BatchContext = BatchContext()

        ctx.set_field_value("amount", 1, 100)
        ctx.set_field_value("cost", 1, 60)
        ctx.set_field_value("order_id", 1, 1)

        # 删除 row_id=1,但保留 order_id
        ctx.delete_row_from_all_fields(1, exclude_fields={"order_id"})

        assert ctx.get_field_value("amount", 1) is None
        assert ctx.get_field_value("cost", 1) is None
        assert ctx.get_field_value("order_id", 1) == 1

    def test_clear(self) -> None:
        """测试清空所有数据"""
        ctx: BatchContext = BatchContext()

        ctx.set_field_value("amount", 1, 100)
        ctx.set_field_value("cost", 1, 60)

        ctx.clear()

        assert ctx.get_field_count() == 0

    def test_get_field_values_for_row(self) -> None:
        """测试批量获取字段值"""
        ctx: BatchContext = BatchContext()

        ctx.set_field_value("amount", 1, 100)
        ctx.set_field_value("cost", 1, 60)

        values = ctx.get_field_values_for_row(1, ["amount", "cost", "missing"])
        assert values == {"amount": 100, "cost": 60, "missing": None}

    def test_get_all_rows_and_field_keys(self) -> None:
        """测试字段行标识集合与字段键列表"""
        ctx: BatchContext = BatchContext()

        assert ctx.get_all_rows_for_field("amount") == set()
        assert ctx.get_field_keys() == set()

        ctx = _build_ctx_with_amounts()
        ctx.set_field_value("cost", 1, 60)

        assert ctx.get_all_rows_for_field("amount") == {1, 2}
        assert ctx.get_field_keys() == {"amount", "cost"}

    def test_get_field_count(self) -> None:
        """测试字段计数"""
        ctx: BatchContext = BatchContext()

        assert ctx.get_field_count() == 0

        ctx.set_field_value("amount", 1, 100)
        assert ctx.get_field_count() == 1

        ctx.set_field_value("cost", 1, 60)
        assert ctx.get_field_count() == 2


# endregion


# region 测试: IREngine 批处理


class TestIREngineBatching:
    """IREngine 批处理测试"""

    def test_batch_processing(
        self,
        simple_model: DemandIr,
        mock_loader: MockDataLoader,
    ) -> None:
        """测试批次处理"""
        builder = PlanBuilder(simple_model)
        plan = builder.build(targets=["order_id", "amount"])

        engine = ScalimEngine(
            demand=simple_model,
            plan=plan,
            batch_size=1,  # 每批只处理1条
        )

        results = engine.run()

        # 主数据源 loader 仅调用一次
        assert mock_loader.call_count["orders"] == 1

        # 结果应该完整
        assert len(results) == 3

    def test_empty_primary_keys(
        self,
        simple_model: DemandIr,
        mock_loader: MockDataLoader,
    ) -> None:
        """测试空主键列表"""
        builder = PlanBuilder(simple_model)
        plan = builder.build(targets=["order_id", "amount"])

        engine = ScalimEngine(
            demand=simple_model,
            plan=plan,
            batch_size=10,
        )

        results = engine.run(main_rows=[])

        assert results == []


class TestRelationDependencyDirection:
    """测试关联条件左右顺序不影响依赖推断"""

    def test_relation_reversed_condition_still_resolves(
        self,
        mock_loader: MockDataLoader,
    ) -> None:
        customers_loader = LoaderIr(
            callable=mock_loader.get_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        )

        orders_source = MainSourceIr(
            source_id="orders",
            loader=mock_loader.get_orders,
        )

        customers_source = SourceIr(
            source_id="customers",
            key=KeyIr(key="customer_id"),
            loader_spec=customers_loader,
        )

        # 反向关联: customers.customer_id = orders.customer_id
        reversed_relation = customers_source["customer_id"].join(orders_source["customer_id"])

        fields = [
            FieldIr(
                field_id="order_id",
                name="订单ID",
                source=orders_source,
                is_primary=True,
            ),
            FieldIr(
                field_id="customer_id",
                name="客户ID",
                source=orders_source,
            ),
            FieldIr(
                field_id="customer_name",
                name="客户名称",
                source=customers_source,
                data_key="customer_name",
                relation=reversed_relation,
            ),
        ]

        demand = DemandIr.from_irs(
            sources=[customers_source],
            fields=fields,
            main_source=orders_source,
        )

        builder = PlanBuilder(demand)
        plan = builder.build(targets=["order_id", "customer_name"])
        assert "customer_id" in plan.field_dependencies.get("customer_name", ())

        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            batch_size=2,
        )

        results = engine.run()
        result_dict = {r["order_id"]: r for r in results}

        assert result_dict[0]["customer_name"] == "Alice"
        assert result_dict[1]["customer_name"] == "Bob"
        assert result_dict[2]["customer_name"] == "Charlie"


# endregion


# region 测试: Adaptive 执行模式


class TestAdaptiveExecution:
    """Adaptive 执行模式测试"""

    @pytest.mark.parametrize(
        "model_fixture,targets,expected_field,expected_values",
        [
            ("simple_model", ["order_id", "amount"], "amount", [100, 200, 300]),
            ("relation_model", ["order_id", "customer_name"], "customer_name", ["Alice", "Bob", "Charlie"]),
        ],
        ids=["basic", "relation"],
    )
    def test_adaptive_mode_variants(
        self,
        request,
        model_fixture: str,
        targets: List[str],
        expected_field: str,
        expected_values: List[object],
    ) -> None:
        model = request.getfixturevalue(model_fixture)
        plan = PlanBuilder(model).build(targets=targets)

        engine = ScalimEngine(
            demand=model,
            plan=plan,
            batch_size=1,
            parallel_mode="adaptive",
            max_workers=2,
        )

        results = engine.run()

        assert len(results) == 3
        result_dict = {r["order_id"]: r for r in results}
        for idx, expected in enumerate(expected_values):
            assert result_dict[idx][expected_field] == expected

    def test_adaptive_vs_sequential_consistency(
        self,
        derived_model: DemandIr,
    ) -> None:
        plan = PlanBuilder(derived_model).build(targets=["order_id", "profit"])

        engine_seq = ScalimEngine(demand=derived_model, plan=plan, batch_size=2, parallel_mode="seq")
        results_seq = engine_seq.run()

        engine_adaptive = ScalimEngine(demand=derived_model, plan=plan, batch_size=2, parallel_mode="adaptive", max_workers=2)
        results_adaptive = engine_adaptive.run()

        assert len(results_seq) == len(results_adaptive) == 3
        seq_dict = {r["order_id"]: r for r in results_seq}
        adaptive_dict = {r["order_id"]: r for r in results_adaptive}

        for pk in [0, 1, 2]:
            assert seq_dict[pk]["profit"] == adaptive_dict[pk]["profit"]

    def test_adaptive_allows_streaming_sink(self, simple_model: DemandIr) -> None:
        plan = PlanBuilder(simple_model).build(targets=["order_id", "amount"])
        engine = ScalimEngine(demand=simple_model, plan=plan, batch_size=2, parallel_mode="adaptive", max_workers=2)

        sink = InMemoryRowSink()
        result = engine.run(sink=sink)

        assert result == []
        assert sink.get_data()

    def test_parallel_mode_thread_process_hard_removed(self, simple_model: DemandIr) -> None:
        plan = PlanBuilder(simple_model).build(targets=["order_id", "amount"])

        with pytest.raises(ValueError, match="parallel_mode='thread' was removed"):
            _ = ScalimEngine(demand=simple_model, plan=plan, parallel_mode="thread")

        with pytest.raises(ValueError, match="parallel_mode='process' was removed"):
            _ = ScalimEngine(demand=simple_model, plan=plan, parallel_mode="process")

    def test_parallel_mode_invalid_value_rejected(self, simple_model: DemandIr) -> None:
        plan = PlanBuilder(simple_model).build(targets=["order_id", "amount"])

        with pytest.raises(ValueError, match="Invalid parallel_mode='nope'"):
            _ = ScalimEngine(demand=simple_model, plan=plan, parallel_mode="nope")


# endregion


# region 测试: 派生字段链 (A -> B -> C)


class TestChainedDerivedFields:
    """测试派生字段链的依赖收集和计算

    验证 pipeline._compute_required_fields 正确收集完整依赖闭包
    场景: C 依赖 B, B 依赖 A (amount), 目标只有 C
    期望: A, B 都应该被包含在 required_fields 中
    """

    @pytest.mark.parametrize(
        "batch_size",
        [10, 1],
        ids=["batch-10", "batch-1"],
    )
    def test_chained_derived_field_target_only_c(
        self,
        chained_derived_model: DemandIr,
        mock_loader: MockDataLoader,
        batch_size: int,
    ) -> None:
        """测试只请求链末端字段 C 时的计算正确性(覆盖不同 batch_size)"""
        builder = PlanBuilder(chained_derived_model)
        # 只请求链末端字段
        plan = builder.build(targets=["order_id", "c_triple_b"])

        engine = ScalimEngine(
            demand=chained_derived_model,
            plan=plan,
            batch_size=batch_size,
        )

        results = engine.run()

        assert len(results) == 3
        result_dict = {r["order_id"]: r for r in results}

        # 验证链式计算正确: c = b * 3 = (a * 2) * 3 = a * 6
        assert result_dict[0]["c_triple_b"] == 600  # 100 * 6
        assert result_dict[1]["c_triple_b"] == 1200  # 200 * 6
        assert result_dict[2]["c_triple_b"] == 1800  # 300 * 6

    def test_chained_derived_field_dependencies_collected(
        self,
        chained_derived_model: DemandIr,
        mock_loader: MockDataLoader,
    ) -> None:
        """测试 PlanBuilder 是否正确收集链式依赖"""
        builder = PlanBuilder(chained_derived_model)
        plan = builder.build(targets=["c_triple_b"])

        # field_order 应该包含完整依赖链: amount, b_double_amount, c_triple_b
        assert "amount" in plan.field_order
        assert "b_double_amount" in plan.field_order
        assert "c_triple_b" in plan.field_order

        # field_specs 也应该包含所有依赖
        assert "amount" in plan.field_specs
        assert "b_double_amount" in plan.field_specs
        assert "c_triple_b" in plan.field_specs


# endregion
