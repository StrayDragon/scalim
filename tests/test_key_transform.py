"""Lookup key normalization tests.

Coverage:
- key.cast (source-level) normalization
- lookup_cast (step-level) normalization
- multi-field composite keys
- multi-level lookup chains
- lookup_cast overrides key.cast
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from scalim.hooks.base import BaseHook, HookManager
from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from scalim.utils.converters import (
    NamedLookupCast,
    auto_normalize_key,
    must_get_seps_values_first_int,
    must_to_int,
    must_to_int_tuple,
)


# region Mock Data Loaders


class MockDataLoaderWithTypes:
    """测试用数据加载器 - 支持类型不匹配场景"""

    def __init__(self) -> None:
        self.orders: Dict[int, Dict[str, Any]] = {
            0: {"order_id": 0, "amount": 100, "customer_id": "100", "region_id": "1", "institution_id": "10"},
            1: {"order_id": 1, "amount": 200, "customer_id": "101", "region_id": "2", "institution_id": "20"},
            2: {"order_id": 2, "amount": 300, "customer_id": "102", "region_id": "1", "institution_id": "20"},
        }

        self.customers: Dict[int, Dict[str, Any]] = {
            100: {"customer_id": 100, "customer_name": "Alice"},
            101: {"customer_id": 101, "customer_name": "Bob"},
            102: {"customer_id": 102, "customer_name": "Charlie"},
        }

        self.mappings: Dict[Tuple[int, int], Dict[str, Any]] = {
            (1, 10): {"region_id": 1, "institution_id": 10, "mapping_name": "mapping_1_10"},
            (2, 20): {"region_id": 2, "institution_id": 20, "mapping_name": "mapping_2_20"},
            (1, 20): {"region_id": 1, "institution_id": 20, "mapping_name": "mapping_1_20"},
        }

    def get_orders(self, order_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        if order_ids:
            return [self.orders[key] for key in order_ids if key in self.orders]
        return list(self.orders.values())

    def get_customers(self, customer_ids_set: Optional[Set[int]] = None) -> Dict[int, Dict[str, Any]]:
        if customer_ids_set:
            return {k: v for k, v in self.customers.items() if k in customer_ids_set}
        return self.customers

    def get_mappings(self, composite_keys: Optional[Set[Tuple[int, int]]] = None) -> Dict[Tuple[int, int], Dict[str, Any]]:
        if composite_keys:
            return {k: v for k, v in self.mappings.items() if k in composite_keys}
        return self.mappings


class MockMultiLevelLoader:
    """测试用数据加载器 - 多级关联场景"""

    def __init__(self) -> None:
        self.orders: Dict[int, Dict[str, Any]] = {
            0: {"order_id": 0, "pay_id": "1000"},
            1: {"order_id": 1, "pay_id": "1001"},
            2: {"order_id": 2, "pay_id": "1002"},
        }

        self.pays: Dict[int, Dict[str, Any]] = {
            1000: {"pay_id": 1000, "pay_method": "credit_card", "country_id": "86"},
            1001: {"pay_id": 1001, "pay_method": "paypal", "country_id": "1"},
            1002: {"pay_id": 1002, "pay_method": "bank_transfer", "country_id": "86"},
        }

        self.countries: Dict[int, Dict[str, Any]] = {
            86: {"country_id": 86, "country_name": "China"},
            1: {"country_id": 1, "country_name": "USA"},
        }

    def get_orders(self, order_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        if order_ids:
            return [self.orders[key] for key in order_ids if key in self.orders]
        return list(self.orders.values())

    def get_pays(self, pay_ids_set: Optional[Set[int]] = None) -> Dict[int, Dict[str, Any]]:
        if pay_ids_set:
            return {k: v for k, v in self.pays.items() if k in pay_ids_set}
        return self.pays

    def get_countries(self, country_ids_set: Optional[Set[int]] = None) -> Dict[int, Dict[str, Any]]:
        if country_ids_set:
            return {k: v for k, v in self.countries.items() if k in country_ids_set}
        return self.countries


class MockCSVFieldLoader:
    """测试用数据加载器 - CSV 多值字段场景"""

    def __init__(self) -> None:
        self.orders: Dict[int, Dict[str, Any]] = {
            0: {"order_id": 0, "group_ids": "10,20,30"},
            1: {"order_id": 1, "group_ids": "20"},
            2: {"order_id": 2, "group_ids": "30,10"},
        }

        self.groups: Dict[int, Dict[str, Any]] = {
            10: {"group_id": 10, "group_name": "Group A"},
            20: {"group_id": 20, "group_name": "Group B"},
            30: {"group_id": 30, "group_name": "Group C"},
        }

    def get_orders(self, order_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        if order_ids:
            return [self.orders[key] for key in order_ids if key in self.orders]
        return list(self.orders.values())

    def get_groups(self, group_ids_set: Optional[Set[int]] = None) -> Dict[int, Dict[str, Any]]:
        if group_ids_set:
            return {k: v for k, v in self.groups.items() if k in group_ids_set}
        return self.groups


# endregion


class MockFloatKeyLoader:
    """测试用数据加载器 - float 关联键告警场景"""

    def __init__(self) -> None:
        self.orders: List[Dict[str, Any]] = [
            {"order_id": 0, "customer_id": 1.0},
            {"order_id": 1, "customer_id": 2.0},
        ]
        self.customers: Dict[int, Dict[str, Any]] = {
            1: {"customer_id": 1, "customer_name": "Alice"},
            2: {"customer_id": 2, "customer_name": "Bob"},
        }

    def get_orders(self, order_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        if order_ids:
            return [row for row in self.orders if row.get("order_id") in order_ids]
        return list(self.orders)

    def get_customers(self, customer_ids_set: Optional[Set[int]] = None) -> Dict[int, Dict[str, Any]]:
        if customer_ids_set:
            return {k: v for k, v in self.customers.items() if k in customer_ids_set}
        return self.customers


@pytest.fixture
def mock_loader_with_types() -> MockDataLoaderWithTypes:
    return MockDataLoaderWithTypes()


@pytest.fixture
def mock_multi_level_loader() -> MockMultiLevelLoader:
    return MockMultiLevelLoader()


@pytest.fixture
def mock_csv_loader() -> MockCSVFieldLoader:
    return MockCSVFieldLoader()


@pytest.fixture
def mock_float_key_loader() -> MockFloatKeyLoader:
    return MockFloatKeyLoader()


def _run_engine(demand: DemandIr, targets: List[str]) -> List[Dict[str, Any]]:
    plan = PlanBuilder(demand).build(targets=targets)
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=2)
    return engine.run()


class _DiagnosticCaptureHook(BaseHook):
    def __init__(self) -> None:
        self.events = []

    def on_diagnostic_warning(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_key_cast_single_field_str_to_int(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_loader_with_types.get_orders)

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id", cast=must_to_int),
        loader_spec=LoaderIr(
            callable=mock_loader_with_types.get_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    relation = orders_source["customer_id"].join(customers_source["customer_id"])

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source=orders_source),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source=customers_source,
            data_key="customer_name",
            relation=relation,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "customer_name"])
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["customer_name"] == "Alice"
    assert result_map[1]["customer_name"] == "Bob"
    assert result_map[2]["customer_name"] == "Charlie"


def test_key_cast_missing_causes_lookup_miss(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_loader_with_types.get_orders)

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=mock_loader_with_types.get_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    relation = orders_source["customer_id"].join(customers_source["customer_id"])

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source=orders_source),
        FieldIr(field_id="customer_name", name="客户名称", source=customers_source, data_key="customer_name", relation=relation),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "customer_name"])
    assert all(row["customer_name"] is None for row in results)


def test_lookup_cast_auto_float_emits_diagnostic_warning(mock_float_key_loader: MockFloatKeyLoader) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_float_key_loader.get_orders)

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=mock_float_key_loader.get_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    lookup_steps = (LookupStepIr(from_field="customer_id", to_source=customers_source, lookup_cast=auto_normalize_key),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source=orders_source),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source=customers_source,
            data_key="customer_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name"])
    hook = _DiagnosticCaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    engine = ScalimEngine(demand=demand, plan=plan, hook_manager=hook_manager, batch_size=2)

    results = engine.run()
    assert all(row["customer_name"] is None for row in results)
    assert len(hook.events) == 1
    assert isinstance(hook.events[0].lookup_key, float)


def test_lookup_cast_auto_non_float_has_no_warning(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_loader_with_types.get_orders)

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=mock_loader_with_types.get_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    lookup_steps = (LookupStepIr(from_field="customer_id", to_source=customers_source, lookup_cast=auto_normalize_key),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source=orders_source),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source=customers_source,
            data_key="customer_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name"])
    hook = _DiagnosticCaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    engine = ScalimEngine(demand=demand, plan=plan, hook_manager=hook_manager, batch_size=2)

    results = engine.run()
    assert all(row["customer_name"] is None for row in results)
    assert hook.events == []


def test_lookup_cast_auto_multi_field_float_warns(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    def _auto_multi_cast(value: object) -> Optional[Tuple[object, ...]]:
        if not isinstance(value, (list, tuple)):
            return None
        converted: List[object] = []
        for item in value:
            normalized = auto_normalize_key(item)
            if normalized is None:
                return None
            converted.append(normalized)
        return tuple(converted)

    lookup_cast = NamedLookupCast("auto", _auto_multi_cast)

    orders_source = MainSourceIr(source_id="orders", loader=mock_loader_with_types.get_orders)
    mapping_source = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "institution_id")),
        loader_spec=LoaderIr(callable=lambda _keys_set=None: {}),  # type: ignore[call-arg]
    )

    lookup_steps = (
        LookupStepIr(
            from_field=("region_id", "institution_id"),
            to_source=mapping_source,
            lookup_cast=lookup_cast,
        ),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="region_id", name="地区ID", source=orders_source),
        FieldIr(field_id="institution_id", name="机构ID", source=orders_source),
        FieldIr(
            field_id="mapping_name",
            name="映射名",
            source=mapping_source,
            data_key="mapping_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[mapping_source], fields=fields, main_source=orders_source)
    plan = PlanBuilder(demand).build(targets=["order_id", "mapping_name"])
    hook = _DiagnosticCaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    engine = ScalimEngine(demand=demand, plan=plan, hook_manager=hook_manager, batch_size=2)

    # 注入 float 复合键,确保触发 tuple 分支
    results = engine.run(
        main_rows=[
            {"order_id": 0, "region_id": 1.0, "institution_id": 10},
            {"order_id": 1, "region_id": 2.0, "institution_id": 20},
        ]
    )
    assert all(row["mapping_name"] is None for row in results)
    assert len(hook.events) == 1


def test_multi_field_key_cast(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_loader_with_types.get_orders)

    mapping_source = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "institution_id"), cast=must_to_int_tuple),
        loader_spec=LoaderIr(
            callable=mock_loader_with_types.get_mappings,
            bindings={
                ("region_id", "institution_id"): BindingIr(
                    key_field=("region_id", "institution_id"),
                    params_builder=lambda ctx: ((), {"composite_keys": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    lookup_steps = (LookupStepIr(from_field=("region_id", "institution_id"), to_source=mapping_source),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="region_id", name="区域ID", source=orders_source),
        FieldIr(field_id="institution_id", name="机构ID", source=orders_source),
        FieldIr(
            field_id="mapping_name",
            name="映射名称",
            source=mapping_source,
            data_key="mapping_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[mapping_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "mapping_name"])
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["mapping_name"] == "mapping_1_10"
    assert result_map[1]["mapping_name"] == "mapping_2_20"
    assert result_map[2]["mapping_name"] == "mapping_1_20"


def test_multi_level_key_cast(mock_multi_level_loader: MockMultiLevelLoader) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_multi_level_loader.get_orders)

    pays_source = SourceIr(
        source_id="pays",
        key=KeyIr(key="pay_id", cast=must_to_int),
        loader_spec=LoaderIr(
            callable=mock_multi_level_loader.get_pays,
            bindings={
                "pay_id": BindingIr(
                    key_field="pay_id",
                    params_builder=lambda ctx: ((), {"pay_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    countries_source = SourceIr(
        source_id="countries",
        key=KeyIr(key="country_id", cast=must_to_int),
        loader_spec=LoaderIr(
            callable=mock_multi_level_loader.get_countries,
            bindings={
                "country_id": BindingIr(
                    key_field="country_id",
                    params_builder=lambda ctx: ((), {"country_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    lookup_steps = (
        LookupStepIr(from_field="pay_id", to_source=pays_source),
        LookupStepIr(from_field="country_id", to_source=countries_source),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="pay_id", name="支付ID", source=orders_source),
        FieldIr(
            field_id="country_name",
            name="国家名称",
            source=countries_source,
            data_key="country_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[pays_source, countries_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "country_name"])
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["country_name"] == "China"
    assert result_map[1]["country_name"] == "USA"
    assert result_map[2]["country_name"] == "China"


def test_lookup_cast_overrides_key_cast(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    def bad_cast(_value: Any) -> Optional[int]:
        raise RuntimeError("key.cast should not be called")

    orders_source = MainSourceIr(source_id="orders", loader=mock_loader_with_types.get_orders)

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id", cast=bad_cast),
        loader_spec=LoaderIr(
            callable=mock_loader_with_types.get_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    lookup_steps = (LookupStepIr(from_field="customer_id", to_source=customers_source, lookup_cast=must_to_int),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source=orders_source),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source=customers_source,
            data_key="customer_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "customer_name"])
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["customer_name"] == "Alice"
    assert result_map[1]["customer_name"] == "Bob"
    assert result_map[2]["customer_name"] == "Charlie"


def test_lookup_cast_csv_first(mock_csv_loader: MockCSVFieldLoader) -> None:
    orders_source = MainSourceIr(source_id="orders", loader=mock_csv_loader.get_orders)

    groups_source = SourceIr(
        source_id="groups",
        key=KeyIr(key="group_id", cast=must_to_int),
        loader_spec=LoaderIr(
            callable=mock_csv_loader.get_groups,
            bindings={
                "group_id": BindingIr(
                    key_field="group_id",
                    params_builder=lambda ctx: ((), {"group_ids_set": ctx.lookup_keys or set()}),
                ),
            },
        ),
    )

    lookup_steps = (LookupStepIr(from_field="group_ids", to_source=groups_source, lookup_cast=must_get_seps_values_first_int),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="group_ids", name="组ID", source=orders_source),
        FieldIr(
            field_id="group_name",
            name="组名",
            source=groups_source,
            data_key="group_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[groups_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "group_name"])
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["group_name"] == "Group A"
    assert result_map[1]["group_name"] == "Group B"
    assert result_map[2]["group_name"] == "Group C"
