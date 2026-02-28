from typing import List, Optional

from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


def make_loader(name: str = "test") -> LoaderIr:
    """为测试创建最小 `LoaderIr`。"""
    return LoaderIr(
        callable=lambda: {},
        bindings={
            name: BindingIr(
                key_field=name,
                params_builder=lambda ctx: ((), {}),
            ),
        },
    )


def make_source(
    source_id: str,
    key_field: str = "id",
    fk_fields: Optional[List[str]] = None,
) -> SourceIr:
    """为测试创建最小 `SourceIr`。"""
    return SourceIr(
        source_id=source_id,
        key=KeyIr(key=key_field),
        loader_spec=make_loader(source_id),
        fk_fields=frozenset(fk_fields or []),
    )


def make_main_source(source_id: str) -> MainSourceIr:
    return MainSourceIr(
        source_id=source_id,
        loader=lambda: [],
    )


def build_simple_model() -> DemandIr:
    """简单模型：单一主数据源，无关联。"""
    source = make_main_source("orders")

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=source, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=source),
        FieldIr(field_id="cost", name="成本", source=source),
    ]

    return DemandIr.from_irs(
        sources=[],
        fields=fields,
        main_source=source,
    )


def build_derived_model() -> DemandIr:
    """派生模型：包含计算字段。"""
    source = make_main_source("orders")

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=source, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=source),
        FieldIr(field_id="cost", name="成本", source=source),
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
        main_source=source,
    )


def build_relation_model() -> DemandIr:
    """关联模型：跨数据源关联。"""
    orders_source = make_main_source("orders")
    customers_source = make_source("customers", key_field="customer_id")

    orders_to_customers = orders_source["customer_id"].join(customers_source["customer_id"])

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=orders_source),
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


def build_multi_level_model() -> DemandIr:
    """多级关联模型：`orders -> pays -> countries`。"""
    orders_source = make_main_source("orders")
    pays_source = make_source("pays", key_field="pay_id", fk_fields=["country_id"])
    countries_source = make_source("countries", key_field="country_id")

    orders_to_countries = (
        orders_source["pay_id"].join(pays_source["pay_id"]).and_(pays_source["country_id"].join(countries_source["country_id"]))
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(
            field_id="country_name",
            name="国家名称",
            source=countries_source,
            data_key="country_name",
            relation=orders_to_countries,
        ),
    ]

    return DemandIr.from_irs(
        sources=[pays_source, countries_source],
        fields=fields,
        main_source=orders_source,
    )


def build_multi_field_model() -> DemandIr:
    """复合键关联模型。"""
    orders_source = make_main_source("orders")
    mapping_source = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "institution_id")),
        loader_spec=LoaderIr(
            callable=lambda: {},
            bindings={
                ("region_id", "institution_id"): BindingIr(
                    key_field=("region_id", "institution_id"),
                    params_builder=lambda ctx: ((), {}),
                ),
            },
        ),
    )

    orders_to_mapping = (
        orders_source["region_id"]
        .join(mapping_source["region_id"])
        .and_(orders_source["institution_id"].join(mapping_source["institution_id"]))
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        FieldIr(field_id="mapping_name", name="映射名称", source=mapping_source, data_key="mapping_name", relation=orders_to_mapping),
        FieldIr(field_id="region_id", name="地区ID", source=orders_source),
        FieldIr(field_id="institution_id", name="机构ID", source=orders_source),
    ]

    return DemandIr.from_irs(
        sources=[mapping_source],
        fields=fields,
        main_source=orders_source,
    )


__all__ = [
    "build_derived_model",
    "build_multi_field_model",
    "build_multi_level_model",
    "build_relation_model",
    "build_simple_model",
    "make_loader",
    "make_main_source",
    "make_source",
]
