# 完整 YAML DSL 示例

当你需要完整 YAML 配置与真实 loader 时使用本示例.

## 文件
- YAML: `references/example-full/ecommerce_report.yaml`

## Loader 实现 (demo_big_data_report)
```python
# source: notebooks/marimo/examples/demo_big_data_report/_loaders.py

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
```

## 框架约束 (校验 + allowlist)
```python
# source: notebooks/marimo/examples/demo_big_data_report/demo_a0_tutor.py

import yaml

    from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator

    # 先加载 YAML 内容
    with open(yaml_path, "r", encoding="utf-8") as _f:
        yaml_config = yaml.safe_load(_f)

    # 使用 ConfigValidator 验证配置
    validator = ConfigValidator()
    try:
        validator.validate(yaml_config)
        print("✅ ConfigValidator 验证通过!")
        validation_passed = True
    except ConfigValidationError as e:
        print(f"❌ ConfigValidator 验证失败: {e}")
        for _err in e.errors[:5]:
            print(f"   - {_err}")
        validation_passed = False

    # 然后使用 YamlDemandLoader 加载
    loader = YamlDemandLoader()
    demand_config = loader.load(str(yaml_path))
```

## 使用 `run()` 运行
```python
# source: notebooks/marimo/examples/demo_big_data_report/demo_a0_tutor.py

from scalim.dsl.by_yaml import run
    from scalim.sinks.sink_memory import InMemoryRowSink

    # 注意: `run()` 需要 `allowlist` 配置
    # 这里我们使用当前目录的 _loaders 模块
    _this_dir = Path(__file__).parent
    _loaders_module = "notebooks.marimo.examples.demo_big_data_report._loaders"

    try:
        sink = InMemoryRowSink()
        result = run(
            str(yaml_path),
            allowed_modules=frozenset([_loaders_module]),
            sink=sink,
        )
        print("✅ `run()` 执行成功!")
        print(f"   总行数: {result.total_rows}")
        print(f"   耗时: {result.duration:.3f}s")
        print(f"   输出路径: {result.output_path or '(内存)'}")
    except Exception as e:
        print(f"⚠️ `run()` 执行失败: {e}")
        print("   (YAML 配置可能引用了未授权的模块)")
        result = None
```
