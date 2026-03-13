"""电商订单报表共享模块

这个模块提供:
1. IR 模型构建函数
2. 目标字段集定义
3. 与 _loaders.py 和 _verification.py 的集成

业务场景说明请参考 _loaders.py
"""

from typing import Any, Dict, List, Optional, Tuple

from scalim.spec.ir import (
    BindingIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    KeyIr,
    LoaderCallContextIr,
    LoaderIr,
    MainSourceIr,
    OrderByKeyIr,
    SourceIr,
    SourceNormalizeIr,
)
from scalim.typedefs import SourceSpecIrCacheMode

from .loaders import (
    ECommerceConfig,
    calc_final_price,
    calc_order_amount,
    calc_profit,
    calc_tax_amount,
    get_config,
    load_categories,
    load_customers,
    load_logistics,
    load_orders,
    load_payment_methods,
    load_products,
    load_promotions,
    load_region_pricing,
    load_regions,
    load_warehouses,
    set_config,
)

# 重新导出
__all__ = [
    "TARGET_FIELDS_BASIC",
    "TARGET_FIELDS_DERIVED",
    "TARGET_FIELDS_FULL",
    "TARGET_FIELDS_RELATIONS",
    "ECommerceConfig",
    "build_ecommerce_model",
    "build_target_sets",
    "get_config",
    "set_config",
]


# ============================================================================
# `Binding` 参数构建器
# ============================================================================


def _default_binding_params(ctx: LoaderCallContextIr) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    ids = ctx.lookup_keys_list or []
    return (), {"ids": ids, "field_keys": list(ctx.field_keys), "is_ref_loader": ctx.is_ref_loader}


def _composite_binding_params(ctx: LoaderCallContextIr) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    ids = ctx.lookup_keys_list or []
    return (), {"ids": ids, "field_keys": list(ctx.field_keys), "is_ref_loader": ctx.is_ref_loader}


# ============================================================================
# 预定义目标字段集
# ============================================================================

TARGET_FIELDS_BASIC = [
    "order_id",
    "quantity",
    "unit_price",
    "discount_rate",
    "order_date",
]

TARGET_FIELDS_RELATIONS = [
    # 单级关联
    "customer_name",
    "customer_level",
    "customer_phone",
    "product_name",
    "product_brand",
    "product_cost",
    "product_category_id",
    "promotion_name",
    "promotion_discount",
    "payment_method_name",
    "logistics_name",
    "logistics_speed",
    # 多级关联
    "category_name",
    "warehouse_name",
    "region_name",
    "region_name_display",
    "region_manager",
    # 复合键关联
    "price_adjustment",
    "shipping_fee",
    "tax_rate",
]

TARGET_FIELDS_DERIVED = [
    "order_amount",
    "profit",
    "tax_amount",
    "final_price",
]

TARGET_FIELDS_FULL = TARGET_FIELDS_BASIC + TARGET_FIELDS_RELATIONS + TARGET_FIELDS_DERIVED


# ============================================================================
# IR 模型构建
# ============================================================================


def build_ecommerce_model(config: Optional[ECommerceConfig] = None) -> DemandIr:
    """构建电商订单报表 IR 模型

    Args:
        config: 数据配置,None 则使用全局配置

    Returns:
        DemandIr 模型
    """
    if config is not None:
        set_config(config)

    # ========================================================================
    # 数据源定义
    # ========================================================================

    main_source = MainSourceIr(
        source_id="orders",
        loader=load_orders,
        order_by=(OrderByKeyIr(field_key="order_id", direction="asc"),),
    )

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=load_customers,
            bindings={"customer_id": BindingIr(key_field="customer_id", params_builder=_default_binding_params)},
        ),
    )

    products_source = SourceIr(
        source_id="products",
        key=KeyIr(key="product_id"),
        loader_spec=LoaderIr(
            callable=load_products,
            bindings={"product_id": BindingIr(key_field="product_id", params_builder=_default_binding_params)},
        ),
        fk_fields=frozenset({"category_id"}),
    )

    categories_source = SourceIr(
        source_id="categories",
        key=KeyIr(key="category_id"),
        loader_spec=LoaderIr(
            callable=load_categories,
            bindings={"category_id": BindingIr(key_field="category_id", params_builder=_default_binding_params)},
        ),
    )

    warehouses_source = SourceIr(
        source_id="warehouses",
        key=KeyIr(key="warehouse_id"),
        loader_spec=LoaderIr(
            callable=load_warehouses,
            bindings={"warehouse_id": BindingIr(key_field="warehouse_id", params_builder=_default_binding_params)},
        ),
        fk_fields=frozenset({"region_id"}),
    )

    regions_source = SourceIr(
        source_id="regions",
        key=KeyIr(key="region_id"),
        loader_spec=LoaderIr(
            callable=load_regions,
            bindings={"region_id": BindingIr(key_field="region_id", params_builder=_default_binding_params)},
        ),
    )

    region_pricing_source = SourceIr(
        source_id="region_pricing",
        key=KeyIr(key=("region_id", "product_category_id")),
        loader_spec=LoaderIr(
            callable=load_region_pricing,
            bindings={
                ("region_id", "product_category_id"): BindingIr(
                    key_field=("region_id", "product_category_id"),
                    params_builder=_composite_binding_params,
                )
            },
        ),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )

    promotions_source = SourceIr(
        source_id="promotions",
        key=KeyIr(key="promotion_id"),
        loader_spec=LoaderIr(
            callable=load_promotions,
            bindings={"promotion_id": BindingIr(key_field="promotion_id", params_builder=_default_binding_params)},
        ),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )

    payment_methods_source = SourceIr(
        source_id="payment_methods",
        key=KeyIr(key="payment_method_id"),
        loader_spec=LoaderIr(
            callable=load_payment_methods,
            bindings={"payment_method_id": BindingIr(key_field="payment_method_id", params_builder=_default_binding_params)},
        ),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="payment_method_id", on_conflict="error"),
    )

    logistics_source = SourceIr(
        source_id="logistics",
        key=KeyIr(key="logistics_id"),
        loader_spec=LoaderIr(
            callable=load_logistics,
            bindings={"logistics_id": BindingIr(key_field="logistics_id", params_builder=_default_binding_params)},
        ),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )

    # ========================================================================
    # 关联关系定义
    # ========================================================================

    # 单级关联
    rel_to_customers = main_source["customer_id"].join(customers_source["customer_id"])
    rel_to_products = main_source["product_id"].join(products_source["product_id"])
    rel_to_promotions = main_source["promotion_id"].join(promotions_source["promotion_id"])
    rel_to_payment = main_source["payment_method_id"].join(payment_methods_source["payment_method_id"])
    rel_to_logistics = main_source["logistics_id"].join(logistics_source["logistics_id"])
    rel_to_warehouses = main_source["warehouse_id"].join(warehouses_source["warehouse_id"])

    # 多级关联: `orders` -> `products` -> `categories`
    rel_to_categories = (
        main_source["product_id"]
        .join(products_source["product_id"])
        .and_(products_source["category_id"].join(categories_source["category_id"]))
    )

    # 多级关联: `orders` -> `warehouses` -> `regions`
    rel_to_regions = (
        main_source["warehouse_id"]
        .join(warehouses_source["warehouse_id"])
        .and_(warehouses_source["region_id"].join(regions_source["region_id"]))
    )

    # 复合键关联: `orders` -> `region_pricing`
    rel_to_region_pricing = (
        main_source["region_id"]
        .join(region_pricing_source["region_id"])
        .and_(main_source["product_category_id"].join(region_pricing_source["product_category_id"]))
    )

    # ========================================================================
    # 字段定义
    # ========================================================================

    fields: List[Any] = [
        # 主键
        FieldIr(field_id="order_id", name="订单ID", source=main_source, is_primary=True),
        # 基础字段
        FieldIr(field_id="quantity", name="数量", source=main_source),
        FieldIr(field_id="unit_price", name="单价", source=main_source),
        FieldIr(field_id="discount_rate", name="折扣率", source=main_source),
        FieldIr(field_id="order_date", name="订单日期", source=main_source),
        # 单级关联 - 客户
        FieldIr(field_id="customer_name", name="客户姓名", source=customers_source, relation=rel_to_customers),
        FieldIr(field_id="customer_level", name="会员等级", source=customers_source, relation=rel_to_customers),
        FieldIr(field_id="customer_phone", name="客户电话", source=customers_source, relation=rel_to_customers),
        # 单级关联 - 产品
        FieldIr(field_id="product_name", name="产品名称", source=products_source, relation=rel_to_products),
        FieldIr(field_id="product_brand", name="产品品牌", source=products_source, relation=rel_to_products),
        FieldIr(field_id="product_cost", name="产品成本", source=products_source, relation=rel_to_products),
        FieldIr(
            field_id="product_category_id",
            name="产品分类ID",
            source=products_source,
            data_key="category_id",
            relation=rel_to_products,
        ),
        # 单级关联 - 促销(可能为空)
        FieldIr(field_id="promotion_name", name="促销名称", source=promotions_source, relation=rel_to_promotions),
        FieldIr(field_id="promotion_discount", name="促销折扣", source=promotions_source, relation=rel_to_promotions),
        # 单级关联 - 支付方式
        FieldIr(field_id="payment_method_name", name="支付方式", source=payment_methods_source, relation=rel_to_payment),
        # 单级关联 - 物流
        FieldIr(field_id="logistics_name", name="物流公司", source=logistics_source, relation=rel_to_logistics),
        FieldIr(field_id="logistics_speed", name="配送时效", source=logistics_source, relation=rel_to_logistics),
        # 多级关联 - 分类
        FieldIr(field_id="category_name", name="产品分类", source=categories_source, relation=rel_to_categories),
        # 多级关联 - 仓库
        FieldIr(field_id="warehouse_name", name="仓库名称", source=warehouses_source, relation=rel_to_warehouses),
        # 多级关联 - 区域
        FieldIr(field_id="region_name", name="区域名称", source=regions_source, relation=rel_to_regions),
        FieldIr(
            field_id="region_name_display", name="区域名称(展示)", source=regions_source, data_key="region_name", relation=rel_to_regions
        ),
        FieldIr(field_id="region_manager", name="区域经理", source=regions_source, relation=rel_to_regions),
        # 复合键关联 - 区域定价
        FieldIr(field_id="price_adjustment", name="价格调整系数", source=region_pricing_source, relation=rel_to_region_pricing),
        FieldIr(field_id="shipping_fee", name="运费", source=region_pricing_source, relation=rel_to_region_pricing),
        FieldIr(field_id="tax_rate", name="税率", source=region_pricing_source, relation=rel_to_region_pricing),
        # 派生字段
        DerivedFieldIr(
            field_id="order_amount", name="订单金额", dependencies=("quantity", "unit_price", "discount_rate"), calculator=calc_order_amount
        ),
        DerivedFieldIr(field_id="profit", name="利润", dependencies=("order_amount", "product_cost", "quantity"), calculator=calc_profit),
        DerivedFieldIr(field_id="tax_amount", name="税费", dependencies=("order_amount", "tax_rate"), calculator=calc_tax_amount),
        DerivedFieldIr(
            field_id="final_price",
            name="最终价格",
            dependencies=("order_amount", "price_adjustment", "shipping_fee"),
            calculator=calc_final_price,
        ),
    ]

    # ========================================================================
    # 构建 DemandIr
    # ========================================================================

    return DemandIr.from_irs(
        sources=[
            customers_source,
            products_source,
            categories_source,
            warehouses_source,
            regions_source,
            region_pricing_source,
            promotions_source,
            payment_methods_source,
            logistics_source,
        ],
        fields=fields,
        main_source=main_source,
        name="ecommerce_order_report",
        batch_size_hint=100,
    )


def build_target_sets() -> Dict[str, List[str]]:
    """构建预定义的目标字段集"""
    return {
        "full": TARGET_FIELDS_FULL,
        "basic": TARGET_FIELDS_BASIC,
        "relations_only": [*TARGET_FIELDS_BASIC, *TARGET_FIELDS_RELATIONS],
        "derived_only": [*TARGET_FIELDS_BASIC, *TARGET_FIELDS_DERIVED],
        "single_level": [
            *TARGET_FIELDS_BASIC,
            "customer_name",
            "customer_phone",
            "product_name",
            "promotion_name",
            "promotion_discount",
            "payment_method_name",
            "logistics_name",
        ],
        "multi_level": [
            *TARGET_FIELDS_BASIC,
            "category_name",
            "region_name",
            "region_name_display",
            "region_manager",
        ],
        "composite_key": [
            *TARGET_FIELDS_BASIC,
            "price_adjustment",
            "shipping_fee",
            "tax_rate",
        ],
    }
