"""订单报表示例模块 - 使用 IR 层直接定义.

这个模块展示了如何使用 Scalim IR 层来定义数据报表需求.

FR 需求覆盖:
- FR002: 字段转换与派生 (profit 计算, order_source 枚举转换)
- FR011: 数据源多种关联方式 (单字段/多表级联/复合主键)
- FR013: 外键类型转换 (KeyIr.cast, lookup_cast)
  - 多级关联: orders → small_groups → big_groups
  - CSV 多值字段: small_group_ids = "10,20,30" 取第一个值
- FR021: 依赖字段剪枝 (PlanBuilder 自动分析)
- FR022: 字段瘦身 (中间字段用完即删)
- FR023: 流式写入 (行级/列级)
- FR031: 事件与钩子系统 (LoggingHook, MetricsHook, TraceHook)
- FR032: 可视化数据流转 (Mermaid 图生成)
"""

import logging
import time
from pathlib import Path
from typing import Any, cast

try:
    import pandas as pd
except ImportError as e:
    msg = "pandas is required for this module, please install it!"
    raise ImportError(msg) from e

from ...spec.ir.binding import BindingIr, LoaderIr
from ...spec.ir.demand import DemandIr
from ...spec.ir.fields import DerivedFieldIr, FieldIr
from ...spec.ir.relations import LookupStepIr
from ...spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from ...typedefs import SourceSpecIrCacheMode
from ...utils.converters import must_get_seps_values_first_int

# 配置 logger
FORMAT = "%(asctime)s | %(message)s"
try:
    from rich.logging import RichHandler

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                enable_link_path=False,
                rich_tracebacks=True,
            )
        ],
    )
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format=FORMAT,
        datefmt="%H:%M:%S",
    )
LOGGER = logging.getLogger()

# 演示配置
RANDOM_X = 0.3  # 模拟 API 延迟


_DATA_DIR = Path(__file__).parent / "data"


class PandasDataLoader:
    """基于pandas的测试数据加载器"""

    def __init__(self, data_dir: Path = _DATA_DIR, random_delay: float = 0.0) -> None:
        """初始化数据加载器.

        Args:
            data_dir: CSV数据文件目录
            random_delay: 随机延迟时间(秒),用于模拟网络延迟
        """
        self.random_delay: float = random_delay
        self.data_dir: Path = data_dir

        # 加载所有数据到DataFrame
        self.orders_df: pd.DataFrame = pd.read_csv(data_dir / "orders.csv")  # pyright: ignore[reportUnknownMemberType]
        self.customers_df: pd.DataFrame = pd.read_csv(data_dir / "customers.csv")  # pyright: ignore[reportUnknownMemberType]
        self.pays_df: pd.DataFrame = pd.read_csv(data_dir / "pays.csv")  # pyright: ignore[reportUnknownMemberType]
        self.countries_df: pd.DataFrame = pd.read_csv(data_dir / "countries.csv")  # pyright: ignore[reportUnknownMemberType]
        self.region_institution_mapping_df: pd.DataFrame = pd.read_csv(data_dir / "region_institution_mapping.csv")  # pyright: ignore[reportUnknownMemberType]
        # FR003: 订单类型表 - 小数据集,适合预加载缓存
        self.order_types_df: pd.DataFrame = pd.read_csv(data_dir / "order_types.csv")  # pyright: ignore[reportUnknownMemberType]
        # FR013: 小组表 - 用于多级关联 + CSV 多值字段示例
        self.small_groups_df: pd.DataFrame = pd.read_csv(data_dir / "small_groups.csv")  # pyright: ignore[reportUnknownMemberType]
        self.big_groups_df: pd.DataFrame = pd.read_csv(data_dir / "big_groups.csv")  # pyright: ignore[reportUnknownMemberType]

    def _add_delay(self) -> None:
        """添加随机延迟以模拟网络请求"""
        if self.random_delay > 0:
            time.sleep(self.random_delay)

    def _df_to_dict(self, df: pd.DataFrame | Any, pk_field_name: str) -> dict[int, dict[str, Any]]:
        """将DataFrame转换为字典格式.

        Args:
            df: pandas DataFrame
            pk_field_name: 主键字段名

        Returns:
            以主键为key的字典
        """
        result: dict[int, dict[str, Any]] = {}
        for _, row in df.iterrows():
            pk = int(row[pk_field_name])
            row_dict = cast("dict[str, Any]", row.to_dict())
            result[pk] = row_dict
        return result

    def _df_to_rows(self, df: pd.DataFrame | Any) -> list[dict[str, Any]]:
        """将DataFrame转换为行列表."""
        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            row_dict = cast("dict[str, Any]", row.to_dict())
            rows.append(row_dict)
        return rows

    def get_orders(
        self,
        begin_time: str,  # pyright: ignore[reportUnusedParameter]
        end_time: str,  # pyright: ignore[reportUnusedParameter]
        page: int = 0,
        page_size: int = 10,
        order_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """获取订单数据.

        Args:
            begin_time: 开始时间
            end_time: 结束时间
            page: 页码
            page_size: 每页大小
            order_ids: 订单ID列表(可选)

        Returns:
            订单数据行列表
        """
        self._add_delay()

        if order_ids:
            df = self.orders_df[self.orders_df["order_id"].isin(order_ids)]
        else:
            start = page * page_size
            end = start + page_size
            df = self.orders_df.iloc[start:end]

        return self._df_to_rows(df)

    def get_customers(self, customer_ids_set: set[int] | None = None, **extra_params: Any) -> dict[int, dict[str, Any]]:  # pyright: ignore[reportUnusedParameter]
        """获取客户数据.

        Args:
            customer_ids_set: 客户ID集合
            **extra_params: 额外参数(未使用)

        Returns:
            客户数据字典
        """
        self._add_delay()

        if customer_ids_set:
            df = self.customers_df[self.customers_df["customer_id"].isin(customer_ids_set)]
        else:
            df = self.customers_df

        return self._df_to_dict(df, "customer_id")

    def get_pays(self, pay_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取支付数据.

        Args:
            pay_ids_set: 支付ID集合

        Returns:
            支付数据字典
        """
        self._add_delay()

        if pay_ids_set:
            df = self.pays_df[self.pays_df["pay_id"].isin(pay_ids_set)]
        else:
            df = self.pays_df

        return self._df_to_dict(df, "pay_id")

    def get_countries(self, country_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取国家数据.

        Args:
            country_ids_set: 国家ID集合

        Returns:
            国家数据字典
        """
        self._add_delay()

        if country_ids_set:
            df = self.countries_df[self.countries_df["country_id"].isin(country_ids_set)]
        else:
            df = self.countries_df

        return self._df_to_dict(df, "country_id")

    def get_order_types(self, type_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取订单类型数据 - FR003 小数据集缓存示例.

        这是一个典型的小数据集:
        - 数据量小 (只有 5 条)
        - 高频访问 (每个订单都需要关联)
        - 数据稳定 (枚举类型不会频繁变化)

        Args:
            type_ids_set: 类型ID集合

        Returns:
            订单类型数据字典
        """
        self._add_delay()

        if type_ids_set:
            df = self.order_types_df[self.order_types_df["type_id"].isin(type_ids_set)]
        else:
            df = self.order_types_df

        return self._df_to_dict(df, "type_id")

    def get_region_institution_mapping(self, composite_keys: set[tuple[int, int]] | None = None) -> dict[tuple[int, int], dict[str, Any]]:
        """获取区域机构映射数据.

        Args:
            composite_keys: 复合键集合 (region_id, institution_id)

        Returns:
            映射数据字典,键为(region_id, institution_id)元组
        """
        self._add_delay()

        if composite_keys:
            # 过滤匹配的复合键
            matches = []
            for region_id, institution_id in composite_keys:
                matched = self.region_institution_mapping_df[
                    (self.region_institution_mapping_df["region_id"] == region_id)
                    & (self.region_institution_mapping_df["institution_id"] == institution_id)
                ]
                matches.append(matched)  # pyright: ignore[reportUnknownMemberType]

            if matches:
                df = pd.concat(matches, ignore_index=True)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            else:
                df = pd.DataFrame()
        else:
            df = self.region_institution_mapping_df

        # 转换为字典,键为(region_id, institution_id)元组
        result: dict[tuple[int, int], dict[str, Any]] = {}
        for _, row in df.iterrows():
            key = (int(row["region_id"]), int(row["institution_id"]))
            row_dict = cast("dict[str, Any]", row.to_dict())
            result[key] = row_dict

        return result

    def get_small_groups(self, group_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取小组数据 - FR013 多级关联示例.

        Args:
            group_ids_set: 小组ID集合

        Returns:
            小组数据字典
        """
        self._add_delay()

        if group_ids_set:
            df = self.small_groups_df[self.small_groups_df["small_group_id"].isin(group_ids_set)]
        else:
            df = self.small_groups_df

        return self._df_to_dict(df, "small_group_id")

    def get_big_groups(self, group_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取大组数据 - FR013 多级关联示例.

        Args:
            group_ids_set: 大组ID集合

        Returns:
            大组数据字典
        """
        self._add_delay()

        if group_ids_set:
            df = self.big_groups_df[self.big_groups_df["big_group_id"].isin(group_ids_set)]
        else:
            df = self.big_groups_df

        return self._df_to_dict(df, "big_group_id")


# 数据加载器
data_loader = PandasDataLoader(random_delay=RANDOM_X)


# region 数据访问层 - 模拟外部API


class Dal:
    """数据访问层 - 模拟数据库访问"""

    def paged_get_order_list(
        self, begin_time: str, end_time: str, page: int = 0, page_size: int = 10, order_ids: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """分页获取订单列表.

        NOTE: 这是一个典型的分页 API,参数由业务决定,框架不应假设
        支持两种模式:
        1. 分页模式: 使用 page 和 page_size 参数
        2. 指定 ID 模式: 使用 order_ids 参数直接获取指定订单
        """
        return data_loader.get_orders(
            begin_time,
            end_time,
            page,
            page_size,
            order_ids,
        )

    def get_country_info_of_concrete_params(self, country_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取国家信息.

        NOTE: 参数名 country_ids_set 是这个 API 的约定,框架不应假设
        """
        return data_loader.get_countries(country_ids_set)


DAL = Dal()


class Bll:
    """业务逻辑层 - 模拟业务 API"""

    def get_pay_info_from_api_of_concrete_params(self, pay_ids_set: set[int] | None = None) -> dict[int, dict[str, Any]]:
        """获取支付信息.

        NOTE: 参数名 pay_ids_set 是这个 API 的约定,框架不应假设
        """
        return data_loader.get_pays(pay_ids_set)

    def get_customer_info_from_api_of_kw_params(
        self, customer_ids_set: set[int] | None = None, **extra_params: Any
    ) -> dict[int, dict[str, Any]]:
        """获取客户信息.

        NOTE: 使用 **kwargs 模式,参数名 customer_ids_set 是这个 API 的约定
        """
        return data_loader.get_customers(customer_ids_set=customer_ids_set, **extra_params)


BLL = Bll()


# endregion


# region IR 模型构建


def build_order_report_model() -> DemandIr:
    """构建订单报表的 IR 模型.

    NOTE: 这里展示了如何使用 IR 层直接定义数据需求
    所有参数构建逻辑都通过 Binding 提供,框架不做任何假设
    """

    # region 定义数据源

    # 订单数据源 (主数据源, 行流加载)
    orders_source = MainSourceIr(
        source_id="orders",
        loader=DAL.paged_get_order_list,
        params={
            "begin_time": "2024-01-01",
            "end_time": "2024-01-07",
            "page": 0,
            "page_size": 10,
        },
    )

    # 支付数据源
    pays_loader = LoaderIr(
        callable=BLL.get_pay_info_from_api_of_concrete_params,
        bindings={
            "pay_id": BindingIr(
                key_field="pay_id",
                params_builder=lambda ctx: ((), {"pay_ids_set": ctx.lookup_keys or set()}),
            ),
        },
    )

    pays_source = SourceIr(
        source_id="pays",
        key=KeyIr(key="pay_id"),
        loader_spec=pays_loader,
        fk_fields=frozenset({"country_id"}),
    )

    # 客户数据源
    customers_loader = LoaderIr(
        callable=BLL.get_customer_info_from_api_of_kw_params,
        bindings={
            "customer_id": BindingIr(
                key_field="customer_id",
                params_builder=lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys or set()}),
            ),
        },
    )

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=customers_loader,
    )

    # 国家数据源
    countries_loader = LoaderIr(
        callable=DAL.get_country_info_of_concrete_params,
        bindings={
            "country_id": BindingIr(
                key_field="country_id",
                params_builder=lambda ctx: ((), {"country_ids_set": ctx.lookup_keys or set()}),
            ),
        },
    )

    countries_source = SourceIr(
        source_id="countries",
        key=KeyIr(key="country_id"),
        loader_spec=countries_loader,
    )

    # FR003: 订单类型数据源 - 小数据集全局缓存示例
    # 订单类型表数据量小(5条)、高频访问、数据稳定,适合预加载缓存
    # cache_mode=SourceDefCacheMode.PRELOAD_FOREVER 表示:
    # - 在 pipeline 开始前无参数调用 loader 加载全部数据
    # - 缓存数据在整个 pipeline 生命周期内有效
    # - 不参与内存优化剪枝
    order_types_loader = LoaderIr(
        callable=data_loader.get_order_types,
        bindings={
            # NOTE: 预加载模式下此 binding 不会被使用,但保留以支持回退到普通模式
            "type_id": BindingIr(
                key_field="type_id",
                params_builder=lambda ctx: ((), {"type_ids_set": ctx.lookup_keys or set()}),
            ),
        },
    )

    order_types_source = SourceIr(
        source_id="order_types",
        key=KeyIr(key="type_id"),
        loader_spec=order_types_loader,
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,  # FR003: 预加载永久缓存
    )

    # 区域机构映射数据源 - 展示复合 key 和多字段 JOIN
    region_institution_mapping_loader = LoaderIr(
        callable=data_loader.get_region_institution_mapping,
        bindings={
            # 使用元组作为键,匹配复合主键
            ("region_id", "institution_id"): BindingIr(
                key_field=("region_id", "institution_id"),
                params_builder=lambda ctx: ((), {"composite_keys": ctx.lookup_keys or set()}),
            ),
        },
    )

    region_institution_mapping_source = SourceIr(
        source_id="region_institution_mapping",
        key=KeyIr(key=("region_id", "institution_id")),
        loader_spec=region_institution_mapping_loader,
    )

    # FR013: 小组数据源 - 多级关联中间表
    # 用于演示: orders → small_groups → big_groups
    small_groups_loader = LoaderIr(
        callable=data_loader.get_small_groups,
        bindings={
            "small_group_id": BindingIr(
                key_field="small_group_id",
                params_builder=lambda ctx: ((), {"group_ids_set": ctx.lookup_keys or set()}),
            ),
        },
    )

    small_groups_source = SourceIr(
        source_id="small_groups",
        key=KeyIr(key="small_group_id"),
        loader_spec=small_groups_loader,
        fk_fields=frozenset({"big_group_id"}),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,  # 小数据集预加载
    )

    # FR013: 大组数据源 - 多级关联目标表
    big_groups_loader = LoaderIr(
        callable=data_loader.get_big_groups,
        bindings={
            "big_group_id": BindingIr(
                key_field="big_group_id",
                params_builder=lambda ctx: ((), {"group_ids_set": ctx.lookup_keys or set()}),
            ),
        },
    )

    big_groups_source = SourceIr(
        source_id="big_groups",
        key=KeyIr(key="big_group_id"),
        loader_spec=big_groups_loader,
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,  # 小数据集预加载
    )

    # endregion

    # region FR011: 预定义关联关系 (可复用)

    # FR011: 单表单字段关联
    orders_to_customers = orders_source["customer_id"].join(customers_source["customer_id"])
    orders_to_pays = orders_source["pay_id"].join(pays_source["pay_id"])

    # FR011: 多表级联关联 (orders → pays → countries)
    orders_to_countries = (
        orders_source["pay_id"].join(pays_source["pay_id"]).and_(pays_source["country_id"].join(countries_source["country_id"]))
    )

    # FR011: 多字段关联 (复合主键)
    orders_to_mapping = (
        orders_source["region_id"]
        .join(region_institution_mapping_source["region_id"])
        .and_(orders_source["institution_id"].join(region_institution_mapping_source["institution_id"]))
    )

    # FR003: 订单类型关联 (小数据集缓存示例)
    orders_to_order_types = orders_source["order_type_id"].join(order_types_source["type_id"])

    # FR013: 多级关联 (订单 → 小组 → 大组) + CSV 多值字段
    # 数据示例:
    #   orders.small_group_ids = "10,20" (CSV 多值字段,取第一个值)
    #   → small_groups[10].big_group_id = 100
    #   → big_groups[100].big_group_name = "大组甲"
    #
    # 转换机制:
    #   1. 第一级: LookupStep.lookup_cast 处理 CSV 多值字段 "10,20" → 10
    #   2. 第二级: 无需转换,数据都是 int 类型
    orders_to_small_groups = orders_source["small_group_ids"].join(small_groups_source["small_group_id"])
    orders_to_big_groups = (
        orders_source["small_group_ids"]
        .join(small_groups_source["small_group_id"])
        .and_(small_groups_source["big_group_id"].join(big_groups_source["big_group_id"]))
    )
    _ = orders_to_small_groups
    _ = orders_to_big_groups

    # endregion

    # region 定义字段

    # 主键字段
    order_id_field = FieldIr(
        field_id="order_id",
        name="订单ID",
        source=orders_source,
        data_key="order_id",
        is_primary=True,
    )

    # 普通字段
    amount_field = FieldIr(
        field_id="amount",
        name="金额",
        source=orders_source,
        data_key="amount",
    )

    cost_field = FieldIr(
        field_id="cost",
        name="成本",
        source=orders_source,
        data_key="cost",
    )

    customer_id_field = FieldIr(
        field_id="customer_id",
        name="客户ID",
        source=orders_source,
        data_key="customer_id",
    )

    pay_id_field = FieldIr(
        field_id="pay_id",
        name="支付ID",
        source=orders_source,
        data_key="pay_id",
    )

    def profit_field_calculator_fn(amount: float, cost: float) -> str:
        return f"{(amount or 0) - (cost or 0):.2f}"

    # FR002: 派生字段 - 利润计算 (多字段派生)
    profit_field = DerivedFieldIr(
        field_id="profit",
        name="利润",
        dependencies=("amount", "cost"),
        calculator=profit_field_calculator_fn,
    )

    # 关联字段 - 客户名称 (使用新API - 预定义关联)
    customer_name_field = FieldIr(
        field_id="customer_name",
        name="客户名称",
        source=customers_source,
        data_key="customer_name",
        relation=orders_to_customers,
    )

    # 关联字段 - 支付方式 (使用新API - 内联定义关联)
    pay_method_field = FieldIr(
        field_id="pay_method",
        name="支付方式",
        source=pays_source,
        data_key="pay_name",
        relation=orders_to_pays,
    )

    # FR002: 值转换字段 - 订单来源 (枚举映射)
    def order_source_transform(value: Any) -> str:
        """订单来源枚举转换"""
        mapping = {1: "小程序", 2: "线下"}
        return mapping.get(value, "其他")

    order_source_field = FieldIr(
        field_id="order_source",
        name="订单来源",
        source=orders_source,
        data_key="order_source",
        transform=order_source_transform,
    )

    # 多级关联字段 - 国家名称 (使用新API - 预定义关联)
    country_name_field = FieldIr(
        field_id="country_name",
        name="国家名称",
        source=countries_source,
        data_key="country_name",
        relation=orders_to_countries,
    )

    # 多字段关联字段 - 映射名称 (使用新API - 预定义关联)
    mapping_name_field = FieldIr(
        field_id="mapping_name",
        name="区域机构映射",
        source=region_institution_mapping_source,
        data_key="mapping_name",
        relation=orders_to_mapping,
    )

    # FR003: 订单类型ID字段 - 外键
    order_type_id_field = FieldIr(
        field_id="order_type_id",
        name="订单类型ID",
        source=orders_source,
        data_key="order_type_id",
    )

    # FR003: 订单类型名称字段 - 从缓存的 order_types 获取
    order_type_name_field = FieldIr(
        field_id="order_type_name",
        name="订单类型名称",
        source=order_types_source,
        data_key="type_name",
        relation=orders_to_order_types,
    )

    # FR013: small_group_ids 原始字段 (CSV 多值,如 "10,20")
    small_group_ids_field = FieldIr(
        field_id="small_group_ids",
        name="小组ID列表",
        source=orders_source,
        data_key="small_group_ids",
    )

    # FR013: 小组名称 - 单级关联 + CSV 多值字段
    # lookup_cast 从 "10,20" 提取第一个值 10
    small_group_name_field = FieldIr(
        field_id="small_group_name",
        name="小组名称",
        source=small_groups_source,
        data_key="small_group_name",
        lookup_steps=(
            LookupStepIr(
                from_field="small_group_ids",
                to_source=small_groups_source,
                lookup_cast=must_get_seps_values_first_int,
            ),
        ),
    )

    # FR013: 大组名称 - 多级关联 + CSV 多值字段
    # 第一级: lookup_cast 从 "10,20" 提取第一个值 10
    # 第二级: 数据都是 int,无需转换
    big_group_name_field = FieldIr(
        field_id="big_group_name",
        name="大组名称",
        source=big_groups_source,
        data_key="big_group_name",
        lookup_steps=(
            LookupStepIr(
                from_field="small_group_ids",
                to_source=small_groups_source,
                lookup_cast=must_get_seps_values_first_int,
            ),
            LookupStepIr(
                from_field="big_group_id",
                to_source=big_groups_source,
            ),
        ),
    )

    # endregion

    # region 构建 DemandModel

    return DemandIr.from_irs(
        sources=[
            pays_source,
            customers_source,
            countries_source,
            region_institution_mapping_source,
            order_types_source,  # FR003: 预加载缓存的数据源
            small_groups_source,  # FR013: 多级关联中间表
            big_groups_source,  # FR013: 多级关联目标表
        ],
        fields=[
            order_id_field,
            amount_field,
            cost_field,
            customer_id_field,
            pay_id_field,
            profit_field,
            customer_name_field,
            pay_method_field,
            order_source_field,
            country_name_field,
            mapping_name_field,
            order_type_id_field,  # FR003: 外键字段
            order_type_name_field,  # FR003: 从缓存获取的字段
            small_group_ids_field,  # FR013: CSV 多值字段原始值
            small_group_name_field,  # FR013: 单级关联 + CSV 多值字段
            big_group_name_field,  # FR013: 多级关联 + CSV 多值字段
        ],
        main_source=orders_source,
    )

    # endregion


# endregion
