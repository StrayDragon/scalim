"""`by_yaml` 输出/聚合相关的枚举 `SSOT`.

约束:
- 运行时需兼容 `Python 3.6`
- 该模块必须保持“向下依赖”(允许被解析层、运行时、自省层(`introspection`)以及 `schema` 生成层依赖),禁止反向依赖运行时实现
"""

from typing import Tuple

OUTPUT_CONTAINER_TYPES: Tuple[str, ...] = (
    "workbook",
    "csv",
)
"""`outputs.*.container.type` 枚举."""


OUTPUT_HEADER_FIELDS_OUTPUT_BY_ENUM: Tuple[str, ...] = (
    "field_id",
    "name",
)
"""`outputs.*.container.header_fields_output_by` 枚举."""


AGG_DISTINCT_ON_OVERFLOW_ENUM: Tuple[str, ...] = (
    "error",
    "truncate",
)
"""`outputs.*.aggregate.distinct_on_overflow` 枚举."""


DEFAULT_AGG_DISTINCT_ON_OVERFLOW: str = "error"
"""`outputs.*.aggregate.distinct_on_overflow` 默认值."""


AGG_RANK_ORDER_ENUM: Tuple[str, ...] = (
    "asc",
    "desc",
)
"""`outputs.*.aggregate.fields.*.<rank>.order` 枚举."""


DEFAULT_AGG_RANK_ORDER: str = "desc"
"""`outputs.*.aggregate.fields.*.<rank>.order` 默认值."""


AGG_RANK_TOP_K_MODE_ENUM: Tuple[str, ...] = (
    "rank",
    "rows",
)
"""`outputs.*.aggregate.fields.*.<rank>.top_k_mode` 枚举."""


DEFAULT_AGG_RANK_TOP_K_MODE: str = "rank"
"""`outputs.*.aggregate.fields.*.<rank>.top_k_mode` 默认值."""


AGG_METRIC_PRODUCER_KEYS: Tuple[str, ...] = (
    "count",
    "sum",
    "min",
    "max",
    "count_true",
    "count_true_gte",
    "count_distinct",
)
"""`aggregate` 指标 `producer_key` 枚举(聚合指标)."""


AGG_RANK_PRODUCER_KEYS: Tuple[str, ...] = (
    "row_number",
    "rank",
    "dense_rank",
)
"""`aggregate` 排名 `producer_key` 枚举(排名字段)."""


AGG_POST_PRODUCER_KEYS: Tuple[str, ...] = (
    "score_by_rank",
    "call_by",
    "compute",
)
"""`aggregate` 聚合后派生字段 `producer_key` 枚举(后置派生字段)."""


__all__ = [
    "AGG_DISTINCT_ON_OVERFLOW_ENUM",
    "AGG_METRIC_PRODUCER_KEYS",
    "AGG_POST_PRODUCER_KEYS",
    "AGG_RANK_ORDER_ENUM",
    "AGG_RANK_PRODUCER_KEYS",
    "AGG_RANK_TOP_K_MODE_ENUM",
    "DEFAULT_AGG_DISTINCT_ON_OVERFLOW",
    "DEFAULT_AGG_RANK_ORDER",
    "DEFAULT_AGG_RANK_TOP_K_MODE",
    "OUTPUT_CONTAINER_TYPES",
    "OUTPUT_HEADER_FIELDS_OUTPUT_BY_ENUM",
]
