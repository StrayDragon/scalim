"""关联键归一化测试.

覆盖范围:
- `key.cast` 的数据源层归一化
- `lookup_cast` 的 step 级归一化
- 多字段复合键
- 多级查找链路
- `lookup_cast` 覆盖 `key.cast`
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from scalim.hooks import BaseHook, HookManager
from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import LookupStepIr
from scalim.spec.ir import KeyIr, LookupCastSpecIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.lookup_casts import lookup_cast_id
from scalim._internal.utils.converters import (
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
    """测试用数据加载器 - `float` 关联键告警场景"""

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


def _bind_main_source(runtime_bindings: RuntimeBindings, source_id: str, loader_fn) -> MainSourceIr:  # type: ignore[no-untyped-def]
    runtime_bindings.main_source_loaders[str(source_id)] = loader_fn
    return MainSourceIr(
        source_id=str(source_id),
        loader_ref=RuntimeHandleIdIr("main_source:{}".format(source_id)),
    )


def _bind_params_builder(  # type: ignore[no-untyped-def]
    runtime_bindings: RuntimeBindings,
    source_id: str,
    key_field,
    params_builder_fn,
) -> BindingIr:
    runtime_bindings.params_builders[(str(source_id), key_field)] = params_builder_fn
    return BindingIr(
        key_field=key_field,
        params_builder_ref=RuntimeHandleIdIr("params_builder:{}:{}".format(source_id, key_field)),
    )


def _bind_source_loader(runtime_bindings: RuntimeBindings, source_id: str, loader_fn, *, bindings=None) -> LoaderIr:  # type: ignore[no-untyped-def]
    runtime_bindings.source_loaders[str(source_id)] = loader_fn
    return LoaderIr(
        callable_ref=RuntimeHandleIdIr("source_loader:{}".format(source_id)),
        bindings=bindings or {},
    )


def _bind_lookup_cast(runtime_bindings: RuntimeBindings, spec: LookupCastSpecIr, *, is_multi: bool, fn) -> None:  # type: ignore[no-untyped-def]
    runtime_bindings.lookup_key_casts[lookup_cast_id(spec, is_multi=is_multi)] = fn


def _run_engine(
    demand: DemandIr,
    targets: List[str],
    runtime_bindings: RuntimeBindings,
    *,
    hook_manager: Optional[HookManager] = None,
    main_rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    plan = PlanBuilder(demand).build(targets=targets)
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, hook_manager=hook_manager, batch_size=2)
    if main_rows is not None:
        return engine.run(main_rows=main_rows)  # type: ignore[arg-type]
    return engine.run()


class _DiagnosticCaptureHook(BaseHook):
    def __init__(self) -> None:
        self.events = []

    def on_diagnostic_warning(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_key_cast_single_field_str_to_int(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_loader_with_types.get_orders)

    customer_id_cast = LookupCastSpecIr(name="must_to_int")
    _bind_lookup_cast(runtime_bindings, customer_id_cast, is_multi=False, fn=must_to_int)
    customer_id_binding = _bind_params_builder(
        runtime_bindings,
        "customers",
        "customer_id",
        lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
    )
    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id", cast=customer_id_cast),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "customers",
            mock_loader_with_types.get_customers,
            bindings={"customer_id": customer_id_binding},
        ),
    )

    relation = orders_source["customer_id"].join(customers_source["customer_id"])

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source_id=customers_source.source_id,
            data_key="customer_name",
            relation=relation,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "customer_name"], runtime_bindings=runtime_bindings)
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["customer_name"] == "Alice"
    assert result_map[1]["customer_name"] == "Bob"
    assert result_map[2]["customer_name"] == "Charlie"


def test_key_cast_missing_causes_lookup_miss(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_loader_with_types.get_orders)

    customer_id_binding = _bind_params_builder(
        runtime_bindings,
        "customers",
        "customer_id",
        lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
    )
    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "customers",
            mock_loader_with_types.get_customers,
            bindings={"customer_id": customer_id_binding},
        ),
    )

    relation = orders_source["customer_id"].join(customers_source["customer_id"])

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="customer_name", name="客户名称", source_id=customers_source.source_id, data_key="customer_name", relation=relation
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "customer_name"], runtime_bindings=runtime_bindings)
    assert all(row["customer_name"] is None for row in results)


def test_lookup_cast_auto_float_emits_diagnostic_warning(mock_float_key_loader: MockFloatKeyLoader) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_float_key_loader.get_orders)

    customer_id_binding = _bind_params_builder(
        runtime_bindings,
        "customers",
        "customer_id",
        lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
    )
    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "customers",
            mock_float_key_loader.get_customers,
            bindings={"customer_id": customer_id_binding},
        ),
    )

    auto_cast = LookupCastSpecIr(name="auto")
    _bind_lookup_cast(runtime_bindings, auto_cast, is_multi=False, fn=auto_normalize_key)
    lookup_steps = (LookupStepIr(from_field="customer_id", to_source_id=customers_source.source_id, lookup_cast=auto_cast),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source_id=customers_source.source_id,
            data_key="customer_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)
    hook = _DiagnosticCaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    results = _run_engine(
        demand,
        targets=["order_id", "customer_name"],
        runtime_bindings=runtime_bindings,
        hook_manager=hook_manager,
    )
    assert all(row["customer_name"] is None for row in results)
    assert len(hook.events) == 1
    assert isinstance(hook.events[0].payload.lookup_key, float)


def test_lookup_cast_auto_non_float_has_no_warning(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_loader_with_types.get_orders)

    customer_id_binding = _bind_params_builder(
        runtime_bindings,
        "customers",
        "customer_id",
        lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
    )
    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "customers",
            mock_loader_with_types.get_customers,
            bindings={"customer_id": customer_id_binding},
        ),
    )

    auto_cast = LookupCastSpecIr(name="auto")
    _bind_lookup_cast(runtime_bindings, auto_cast, is_multi=False, fn=auto_normalize_key)
    lookup_steps = (LookupStepIr(from_field="customer_id", to_source_id=customers_source.source_id, lookup_cast=auto_cast),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source_id=customers_source.source_id,
            data_key="customer_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)
    hook = _DiagnosticCaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    results = _run_engine(
        demand,
        targets=["order_id", "customer_name"],
        runtime_bindings=runtime_bindings,
        hook_manager=hook_manager,
    )
    assert all(row["customer_name"] is None for row in results)
    assert hook.events == []


def test_lookup_cast_auto_multi_field_float_warns(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    runtime_bindings = RuntimeBindings()

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

    auto_cast = LookupCastSpecIr(name="auto")
    _bind_lookup_cast(runtime_bindings, auto_cast, is_multi=True, fn=_auto_multi_cast)

    orders_source = _bind_main_source(runtime_bindings, "orders", mock_loader_with_types.get_orders)
    mapping_source = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "institution_id")),
        loader_spec=_bind_source_loader(runtime_bindings, "mapping", (lambda _keys_set=None: {})),  # type: ignore[no-any-return]
    )

    lookup_steps = (
        LookupStepIr(
            from_field=("region_id", "institution_id"),
            to_source_id=mapping_source.source_id,
            lookup_cast=auto_cast,
        ),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="region_id", name="地区ID", source_id=orders_source.source_id),
        FieldIr(field_id="institution_id", name="机构ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="mapping_name",
            name="映射名",
            source_id=mapping_source.source_id,
            data_key="mapping_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[mapping_source], fields=fields, main_source=orders_source)
    hook = _DiagnosticCaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    # 注入 `float` 复合键,确保触发 `tuple` 分支
    results = _run_engine(
        demand,
        targets=["order_id", "mapping_name"],
        runtime_bindings=runtime_bindings,
        hook_manager=hook_manager,
        main_rows=[
            {"order_id": 0, "region_id": 1.0, "institution_id": 10},
            {"order_id": 1, "region_id": 2.0, "institution_id": 20},
        ],
    )
    assert all(row["mapping_name"] is None for row in results)
    assert len(hook.events) == 1


def test_multi_field_key_cast(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_loader_with_types.get_orders)

    mapping_key_cast = LookupCastSpecIr(name="must_to_int_tuple")
    _bind_lookup_cast(runtime_bindings, mapping_key_cast, is_multi=True, fn=must_to_int_tuple)
    mapping_binding = _bind_params_builder(
        runtime_bindings,
        "mapping",
        ("region_id", "institution_id"),
        lambda ctx: ((), {"composite_keys": ctx.lookup_keys or set()}),
    )
    mapping_source = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "institution_id"), cast=mapping_key_cast),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "mapping",
            mock_loader_with_types.get_mappings,
            bindings={("region_id", "institution_id"): mapping_binding},
        ),
    )

    lookup_steps = (LookupStepIr(from_field=("region_id", "institution_id"), to_source_id=mapping_source.source_id),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="region_id", name="区域ID", source_id=orders_source.source_id),
        FieldIr(field_id="institution_id", name="机构ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="mapping_name",
            name="映射名称",
            source_id=mapping_source.source_id,
            data_key="mapping_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[mapping_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "mapping_name"], runtime_bindings=runtime_bindings)
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["mapping_name"] == "mapping_1_10"
    assert result_map[1]["mapping_name"] == "mapping_2_20"
    assert result_map[2]["mapping_name"] == "mapping_1_20"


def test_multi_level_key_cast(mock_multi_level_loader: MockMultiLevelLoader) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_multi_level_loader.get_orders)

    to_int_cast = LookupCastSpecIr(name="must_to_int")
    _bind_lookup_cast(runtime_bindings, to_int_cast, is_multi=False, fn=must_to_int)
    pay_id_binding = _bind_params_builder(
        runtime_bindings,
        "pays",
        "pay_id",
        lambda ctx: ((), {"pay_ids_set": ctx.lookup_keys or set()}),
    )
    pays_source = SourceIr(
        source_id="pays",
        key=KeyIr(key="pay_id", cast=to_int_cast),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "pays",
            mock_multi_level_loader.get_pays,
            bindings={"pay_id": pay_id_binding},
        ),
    )

    country_id_binding = _bind_params_builder(
        runtime_bindings,
        "countries",
        "country_id",
        lambda ctx: ((), {"country_ids_set": ctx.lookup_keys or set()}),
    )
    countries_source = SourceIr(
        source_id="countries",
        key=KeyIr(key="country_id", cast=to_int_cast),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "countries",
            mock_multi_level_loader.get_countries,
            bindings={"country_id": country_id_binding},
        ),
    )

    lookup_steps = (
        LookupStepIr(from_field="pay_id", to_source_id=pays_source.source_id),
        LookupStepIr(from_field="country_id", to_source_id=countries_source.source_id),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="pay_id", name="支付ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="country_name",
            name="国家名称",
            source_id=countries_source.source_id,
            data_key="country_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[pays_source, countries_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "country_name"], runtime_bindings=runtime_bindings)
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["country_name"] == "China"
    assert result_map[1]["country_name"] == "USA"
    assert result_map[2]["country_name"] == "China"


def test_lookup_cast_overrides_key_cast(mock_loader_with_types: MockDataLoaderWithTypes) -> None:
    def bad_cast(_value: Any) -> Optional[int]:
        raise RuntimeError("key.cast should not be called")

    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_loader_with_types.get_orders)

    bad_cast_spec = LookupCastSpecIr(name="bad_cast")
    _bind_lookup_cast(runtime_bindings, bad_cast_spec, is_multi=False, fn=bad_cast)
    customer_id_binding = _bind_params_builder(
        runtime_bindings,
        "customers",
        "customer_id",
        lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
    )
    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id", cast=bad_cast_spec),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "customers",
            mock_loader_with_types.get_customers,
            bindings={"customer_id": customer_id_binding},
        ),
    )

    to_int_cast = LookupCastSpecIr(name="must_to_int")
    _bind_lookup_cast(runtime_bindings, to_int_cast, is_multi=False, fn=must_to_int)
    lookup_steps = (LookupStepIr(from_field="customer_id", to_source_id=customers_source.source_id, lookup_cast=to_int_cast),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="customer_name",
            name="客户名称",
            source_id=customers_source.source_id,
            data_key="customer_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "customer_name"], runtime_bindings=runtime_bindings)
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["customer_name"] == "Alice"
    assert result_map[1]["customer_name"] == "Bob"
    assert result_map[2]["customer_name"] == "Charlie"


def test_lookup_cast_csv_first(mock_csv_loader: MockCSVFieldLoader) -> None:
    runtime_bindings = RuntimeBindings()
    orders_source = _bind_main_source(runtime_bindings, "orders", mock_csv_loader.get_orders)

    to_int_cast = LookupCastSpecIr(name="must_to_int")
    _bind_lookup_cast(runtime_bindings, to_int_cast, is_multi=False, fn=must_to_int)
    group_id_binding = _bind_params_builder(
        runtime_bindings,
        "groups",
        "group_id",
        lambda ctx: ((), {"group_ids_set": ctx.lookup_keys or set()}),
    )
    groups_source = SourceIr(
        source_id="groups",
        key=KeyIr(key="group_id", cast=to_int_cast),
        loader_spec=_bind_source_loader(
            runtime_bindings,
            "groups",
            mock_csv_loader.get_groups,
            bindings={"group_id": group_id_binding},
        ),
    )

    csv_first = LookupCastSpecIr(name="sep_first")
    _bind_lookup_cast(runtime_bindings, csv_first, is_multi=False, fn=must_get_seps_values_first_int)
    lookup_steps = (LookupStepIr(from_field="group_ids", to_source_id=groups_source.source_id, lookup_cast=csv_first),)

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="group_ids", name="组ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="group_name",
            name="组名",
            source_id=groups_source.source_id,
            data_key="group_name",
            lookup_steps=lookup_steps,
        ),
    ]

    demand = DemandIr.from_irs(sources=[groups_source], fields=fields, main_source=orders_source)

    results = _run_engine(demand, targets=["order_id", "group_name"], runtime_bindings=runtime_bindings)
    result_map = {row["order_id"]: row for row in results}

    assert result_map[0]["group_name"] == "Group A"
    assert result_map[1]["group_name"] == "Group B"
    assert result_map[2]["group_name"] == "Group C"
