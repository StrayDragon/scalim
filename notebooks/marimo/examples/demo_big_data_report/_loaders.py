"""电商订单报表数据加载器

这个模块提供具有业务意义的合成数据,用于展示 Scalim 框架的关联能力.

业务场景: 电商平台订单报表

```text
- 订单表 (orders): 主表,包含订单基本信息
- 客户表 (customers): 客户信息
- 产品表 (products): 产品信息
- 产品分类表 (categories): 产品分类(多级关联: orders -> products -> categories)
- 仓库表 (warehouses): 仓库信息
- 区域表 (regions): 区域信息(多级关联: orders -> warehouses -> regions)
- 区域定价表 (region_pricing): 复合键关联
- 促销活动表 (promotions): 促销活动(小表,预加载)
- 支付方式表 (payment_methods): 支付方式(小表,预加载)
- 物流公司表 (logistics): 物流公司(小表,预加载)

关联关系:
1. 单级关联: orders -> customers (order.customer_id = customer.customer_id)
2. 单级关联: orders -> products (order.product_id = product.product_id)
3. 多级关联: orders -> products -> categories (2级链路)
4. 多级关联: orders -> warehouses -> regions (2级链路)
5. 复合键关联: orders -> region_pricing (region_id, product_category_id)
6. 小表关联: orders -> promotions, payment_methods, logistics
```
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# ============================================================================
# 配置常量 - 增大默认数据量用于更有效的集成测试
# ============================================================================

DEFAULT_ORDER_COUNT = 2000  # 增大到 2000 条以更好地测试批处理
DEFAULT_CUSTOMER_COUNT = 500
DEFAULT_PRODUCT_COUNT = 200
DEFAULT_CATEGORY_COUNT = 20
DEFAULT_WAREHOUSE_COUNT = 15
DEFAULT_REGION_COUNT = 15
DEFAULT_PROMOTION_COUNT = 15
DEFAULT_PAYMENT_METHOD_COUNT = 5
DEFAULT_LOGISTICS_COUNT = 10

# 预定义配置规模
SCALE_SMALL = "small"  # 100 订单 - 快速测试
SCALE_MEDIUM = "medium"  # 500 订单 - 常规演示
SCALE_LARGE = "large"  # 2000 订单 - 完整测试
SCALE_STRESS = "stress"  # 10000 订单 - 压力测试


@dataclass(frozen=True)
class ECommerceConfig:
    """电商数据配置

    预定义规模:
    - `small`: 100 订单, 适合快速测试
    - `medium`: 500 订单, 适合常规演示
    - `large`: 2000 订单, 适合完整集成测试
    - `stress`: 10000 订单, 适合压力测试
    """

    order_count: int = DEFAULT_ORDER_COUNT
    customer_count: int = DEFAULT_CUSTOMER_COUNT
    product_count: int = DEFAULT_PRODUCT_COUNT
    category_count: int = DEFAULT_CATEGORY_COUNT
    warehouse_count: int = DEFAULT_WAREHOUSE_COUNT
    region_count: int = DEFAULT_REGION_COUNT
    promotion_count: int = DEFAULT_PROMOTION_COUNT
    payment_method_count: int = DEFAULT_PAYMENT_METHOD_COUNT
    logistics_count: int = DEFAULT_LOGISTICS_COUNT

    @classmethod
    def from_scale(cls, scale: str) -> "ECommerceConfig":
        configs = {
            SCALE_SMALL: cls(order_count=100, customer_count=50, product_count=50),
            SCALE_MEDIUM: cls(order_count=500, customer_count=200, product_count=100),
            SCALE_LARGE: cls(order_count=2000, customer_count=500, product_count=200),
            SCALE_STRESS: cls(order_count=10000, customer_count=2000, product_count=500),
        }
        return configs.get(scale, cls())


# 全局配置实例
_CONFIG = ECommerceConfig()


def set_config(config: ECommerceConfig) -> None:
    """设置全局配置"""
    global _CONFIG
    _CONFIG = config


def get_config() -> ECommerceConfig:
    """获取全局配置"""
    return _CONFIG


# ============================================================================
# 数据生成辅助函数
# ============================================================================

_CUSTOMER_PREFIXES = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
_CUSTOMER_SUFFIXES = ["明", "华", "强", "伟", "芳", "娟", "敏", "静", "丽", "勇"]

_PRODUCT_ADJECTIVES = ["高端", "精品", "经典", "时尚", "智能", "便携", "专业", "豪华", "简约", "创新"]
_PRODUCT_NOUNS = ["手机", "电脑", "耳机", "键盘", "显示器", "平板", "音箱", "手表", "相机", "充电器"]

_CATEGORY_NAMES = [
    "数码电子",
    "家用电器",
    "服装鞋帽",
    "食品饮料",
    "美妆护肤",
    "家居日用",
    "运动户外",
    "图书音像",
    "母婴用品",
    "汽车用品",
    "办公文具",
    "珠宝饰品",
    "宠物用品",
    "医疗保健",
    "玩具乐器",
    "生鲜果蔬",
    "箱包皮具",
    "钟表眼镜",
    "厨房用具",
    "五金工具",
]

_CITY_NAMES = [
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "武汉",
    "成都",
    "西安",
    "重庆",
    "苏州",
    "天津",
    "郑州",
    "长沙",
    "青岛",
]

_PROMOTION_NAMES = [
    "双十一狂欢",
    "618大促",
    "年货节",
    "开学季",
    "情人节特惠",
    "五一钜惠",
    "国庆特卖",
    "新品首发",
    "会员专享",
    "限时秒杀",
]

_PAYMENT_METHODS = ["支付宝", "微信支付", "银行卡", "信用卡", "货到付款"]

_LOGISTICS_NAMES = ["顺丰速运", "圆通快递", "中通快递", "韵达快递", "申通快递", "京东物流", "菜鸟驿站", "德邦快递"]


def _safe_index(lst: List[str], idx: int) -> str:
    return lst[idx % len(lst)]


# ============================================================================
# 订单表 (主表)
# ============================================================================


def load_orders(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> List[Dict[str, Any]]:
    """加载订单数据(主数据源)"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    order_ids: Iterable[int] = range(cfg.order_count) if (ids is None or len(ids) == 0) else ids

    result: List[Dict[str, Any]] = []
    for i in order_ids:
        order_id = 1001 + i

        customer_id = i % cfg.customer_count
        product_id = i % cfg.product_count
        warehouse_id = (i * 3) % cfg.warehouse_count
        promotion_id = i % cfg.promotion_count if (i % 5 != 0) else None
        payment_method_id = i % cfg.payment_method_count
        logistics_id = i % cfg.logistics_count

        region_id = warehouse_id % cfg.region_count
        product_category_id = product_id % cfg.category_count

        quantity = 1 + i % 10
        base_price = Decimal("99.00") + Decimal(str(product_id * 10))
        unit_price = float(base_price)
        discount_rate = 0.8 + (i % 5) * 0.05

        day_of_year = (i % 365) + 1
        month = (day_of_year - 1) // 30 + 1
        day = (day_of_year - 1) % 30 + 1
        if month > 12:
            month = 12
        order_date = "2024-{:02d}-{:02d}".format(month, min(day, 28))

        row: Dict[str, Any] = {
            "order_id": order_id,
            "customer_id": customer_id,
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "promotion_id": promotion_id,
            "payment_method_id": payment_method_id,
            "logistics_id": logistics_id,
            "region_id": region_id,
            "product_category_id": product_category_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount_rate": discount_rate,
            "order_date": order_date,
        }
        result.append(row)

    return result


# ============================================================================
# 客户表
# ============================================================================


def load_customers(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载客户数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    customer_ids: Iterable[int] = range(cfg.customer_count) if ids is None else ids

    levels = ["普通", "银卡", "金卡", "钻石"]

    result: Dict[int, Dict[str, Any]] = {}
    for cid in customer_ids:
        prefix = _safe_index(_CUSTOMER_PREFIXES, cid)
        suffix = _safe_index(_CUSTOMER_SUFFIXES, cid // len(_CUSTOMER_PREFIXES))
        name = prefix + suffix

        level = levels[cid % len(levels)]
        phone = "138{:08d}".format(cid * 12345 % 100000000)

        reg_day = (cid * 7) % 365 + 1
        reg_month = (reg_day - 1) // 30 + 1
        reg_date = "2023-{:02d}-{:02d}".format(min(reg_month, 12), (reg_day - 1) % 28 + 1)

        result[cid] = {
            "customer_id": cid,
            "customer_name": name,
            "customer_level": level,
            "customer_phone": phone,
            "registration_date": reg_date,
        }

    return result


def load_customers_by_rows(
    rows: Optional[List[Dict[str, Any]]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """`rows` 模式示例: 从 `batch_rows` 中提取 `customer_id` 后复用 `load_customers`."""
    _ = field_keys
    _ = is_ref_loader

    if not rows:
        return {}

    customer_ids: Set[int] = set()
    for row in rows:
        customer_id = row.get("customer_id")
        if customer_id is None:
            continue
        try:
            customer_ids.add(int(customer_id))
        except (TypeError, ValueError):
            continue

    if not customer_ids:
        return {}

    return load_customers(ids=sorted(customer_ids), field_keys=field_keys, is_ref_loader=is_ref_loader)


# ============================================================================
# 产品表
# ============================================================================


def load_products(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载产品数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    product_ids: Iterable[int] = range(cfg.product_count) if ids is None else ids

    brands = ["华为", "苹果", "小米", "三星", "联想", "戴尔", "索尼", "佳能", "飞利浦", "松下"]

    result: Dict[int, Dict[str, Any]] = {}
    for pid in product_ids:
        adj = _safe_index(_PRODUCT_ADJECTIVES, pid)
        noun = _safe_index(_PRODUCT_NOUNS, pid // len(_PRODUCT_ADJECTIVES))
        name = adj + noun

        category_id = pid % cfg.category_count
        brand = _safe_index(brands, pid)
        cost = float(Decimal("50.00") + Decimal(str(pid * 5)))

        result[pid] = {
            "product_id": pid,
            "product_name": name,
            "category_id": category_id,
            "product_brand": brand,
            "product_cost": cost,
        }

    return result


# ============================================================================
# 产品分类表
# ============================================================================


def load_categories(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载产品分类数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    category_ids: Iterable[int] = range(cfg.category_count) if ids is None else ids

    result: Dict[int, Dict[str, Any]] = {}
    for cid in category_ids:
        name = _safe_index(_CATEGORY_NAMES, cid)
        level = (cid % 3) + 1
        parent_id = cid // 3 if cid > 0 else None

        result[cid] = {
            "category_id": cid,
            "category_name": name,
            "category_level": level,
            "parent_category_id": parent_id,
        }

    return result


# ============================================================================
# 仓库表
# ============================================================================


def load_warehouses(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载仓库数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    warehouse_ids: Iterable[int] = range(cfg.warehouse_count) if ids is None else ids

    result: Dict[int, Dict[str, Any]] = {}
    for wid in warehouse_ids:
        city = _safe_index(_CITY_NAMES, wid)
        name = "{}仓库-{}号".format(city, wid + 1)
        region_id = wid % cfg.region_count
        capacity = 10000 + wid * 1000

        result[wid] = {
            "warehouse_id": wid,
            "warehouse_name": name,
            "region_id": region_id,
            "warehouse_capacity": capacity,
        }

    return result


# ============================================================================
# 区域表
# ============================================================================


def load_regions(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载区域数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    region_ids: Iterable[int] = range(cfg.region_count) if ids is None else ids

    result: Dict[int, Dict[str, Any]] = {}
    for rid in region_ids:
        city = _safe_index(_CITY_NAMES, rid)
        code = "RG-{:03d}".format(rid)
        manager = _safe_index(_CUSTOMER_PREFIXES, rid) + "经理"

        result[rid] = {
            "region_id": rid,
            "region_name": city + "区域",
            "region_code": code,
            "region_manager": manager,
        }

    return result


# ============================================================================
# 区域产品定价表 (复合键)
# ============================================================================


def load_region_pricing(
    ids: Optional[List[Tuple[int, int]]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """加载区域产品定价数据(复合主键)"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()

    if ids is None:
        composite_keys: Iterable[Tuple[int, int]] = ((r, c) for r in range(cfg.region_count) for c in range(cfg.category_count))
    else:
        composite_keys = ids

    result: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for region_id, category_id in composite_keys:
        adjustment = 0.9 + ((region_id + category_id) % 5) * 0.05
        shipping = 5.0 + region_id * 2.0
        tax = 0.03 + (category_id % 5) * 0.02

        result[(region_id, category_id)] = {
            "region_id": region_id,
            "product_category_id": category_id,
            "price_adjustment": round(adjustment, 2),
            "shipping_fee": round(shipping, 2),
            "tax_rate": round(tax, 3),
        }

    return result


# ============================================================================
# 促销活动表 (小表)
# ============================================================================


def load_promotions(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载促销活动数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    promotion_ids: Iterable[int] = range(cfg.promotion_count) if ids is None else ids

    result: Dict[int, Dict[str, Any]] = {}
    for pid in promotion_ids:
        name = _safe_index(_PROMOTION_NAMES, pid)
        discount = 0.5 + (pid % 10) * 0.05

        start_month = (pid % 12) + 1
        end_month = min(start_month + 1, 12)

        result[pid] = {
            "promotion_id": pid,
            "promotion_name": name,
            "promotion_discount": round(discount, 2),
            "promotion_start": "2024-{:02d}-01".format(start_month),
            "promotion_end": "2024-{:02d}-28".format(end_month),
        }

    return result


# ============================================================================
# 支付方式表 (小表)
# ============================================================================


def load_payment_methods(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载支付方式数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    method_ids: Iterable[int] = range(cfg.payment_method_count) if ids is None else ids

    fee_rates = [0.002, 0.002, 0.003, 0.005, 0.0]

    result: Dict[int, Dict[str, Any]] = {}
    for mid in method_ids:
        name = _safe_index(_PAYMENT_METHODS, mid)
        fee_rate = fee_rates[mid % len(fee_rates)]

        result[mid] = {
            "payment_method_id": mid,
            "payment_method_name": name,
            "payment_fee_rate": fee_rate,
        }

    return result


# ============================================================================
# 物流公司表 (小表)
# ============================================================================


def load_logistics(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """加载物流公司数据"""
    _ = is_ref_loader
    _ = field_keys

    cfg = get_config()
    logistics_ids: Iterable[int] = range(cfg.logistics_count) if ids is None else ids

    result: Dict[int, Dict[str, Any]] = {}
    for lid in logistics_ids:
        name = _safe_index(_LOGISTICS_NAMES, lid)
        speed = 1 + (lid % 5)
        rating = 3.0 + (lid % 5) * 0.5

        result[lid] = {
            "logistics_id": lid,
            "logistics_name": name,
            "logistics_speed": speed,
            "logistics_rating": round(rating, 1),
        }

    return result


# ============================================================================
# 派生字段计算器
# ============================================================================


def calc_order_amount(**kwargs: Any) -> Optional[float]:
    """计算订单金额 = 数量 * 单价 * 折扣率"""
    quantity = kwargs.get("quantity")
    unit_price = kwargs.get("unit_price")
    discount_rate = kwargs.get("discount_rate")

    if quantity is None or unit_price is None or discount_rate is None:
        return None

    try:
        return round(float(quantity) * float(unit_price) * float(discount_rate), 2)
    except (TypeError, ValueError):
        return None


def calc_profit(**kwargs: Any) -> Optional[float]:
    """计算利润 = 订单金额 - 成本 * 数量"""
    order_amount = kwargs.get("order_amount")
    product_cost = kwargs.get("product_cost")
    quantity = kwargs.get("quantity")

    if order_amount is None or product_cost is None or quantity is None:
        return None

    try:
        return round(float(order_amount) - float(product_cost) * float(quantity), 2)
    except (TypeError, ValueError):
        return None


def calc_tax_amount(**kwargs: Any) -> Optional[float]:
    """计算税费 = 订单金额 * 税率"""
    order_amount = kwargs.get("order_amount")
    tax_rate = kwargs.get("tax_rate")

    if order_amount is None or tax_rate is None:
        return None

    try:
        return round(float(order_amount) * float(tax_rate), 2)
    except (TypeError, ValueError):
        return None


def calc_final_price(**kwargs: Any) -> Optional[float]:
    """计算最终价格 = 订单金额 * 区域调整系数 + 运费"""
    order_amount = kwargs.get("order_amount")
    price_adjustment = kwargs.get("price_adjustment")
    shipping_fee = kwargs.get("shipping_fee")

    if order_amount is None or price_adjustment is None or shipping_fee is None:
        return None

    try:
        return round(float(order_amount) * float(price_adjustment) + float(shipping_fee), 2)
    except (TypeError, ValueError):
        return None
