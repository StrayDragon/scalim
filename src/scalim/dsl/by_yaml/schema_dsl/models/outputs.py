from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, ClassVar, Dict, Optional, Tuple

from ..constants import (
    DEFAULT_OUTPUT_ENCODING,
    DEFAULT_OUTPUT_HEADER_BY,
    DEFAULT_OUTPUT_INCLUDE_HEADER,
    DEFAULT_OUTPUT_STREAMING,
    FIELD_ID_STRING_SCHEMA,
    schema_meta,
    schema_omit,
)

_OUTPUT_NAME_SCHEMA = {
    **FIELD_ID_STRING_SCHEMA,
    "description": "输出标识(name)",
    "markdownDescription": (
        "输出标识(name).\n\n- 必填且唯一(供 `from` 引用)\n- 命名规则与 field_id 一致: 字母/数字/下划线, 首字符为字母或下划线"
    ),
    "examples": ["detail", "direct_detail", "by_cs"],
}

_FIELD_REF_OR_ALIAS_SCHEMA = {"anyOf": [FIELD_ID_STRING_SCHEMA, {"type": "object"}]}
_FIELD_REF_LIST_ITEM_SCHEMA = {
    "anyOf": [
        FIELD_ID_STRING_SCHEMA,
        {"type": "object"},
        {
            "type": "array",
            "items": _FIELD_REF_OR_ALIAS_SCHEMA,
            "minItems": 1,
        },
    ]
}
_AGG_OUT_FIELD_NAME_SCHEMA = {
    "name": {
        "type": "string",
        "minLength": 1,
        "description": "可选:表头显示名(仅对 aggregate 字段生效)",
        "markdownDescription": (
            "可选:表头显示名.\n\n"
            "- 仅对 `outputs.*.aggregate.fields.*` 的字段生效\n"
            "- 仅在 `outputs.*.container.header_fields_output_by: name` 时输出该 name\n"
            "- 允许重复 name(用于复刻重复表头合同)\n"
            "- 缺省/为空时回退为 out_field_id"
        ),
        "examples": ["订单量", "积分", "排名"],
    }
}


@dataclass(frozen=True)
class OutputContainerConfig:
    SCHEMA_NAME: ClassVar[str] = "output_container"
    """输出容器配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("type", "path")
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    type: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="输出容器类型(workbook/csv)",
            md=("输出容器类型.\n\n- `workbook`: Excel 工作簿容器(支持多 sheet)\n- `csv`: CSV 文件"),
            choices=["workbook", "csv"],
            examples=["workbook"],
        ),
    )
    """输出容器类型."""

    path: str = dataclass_field(
        default="",
        metadata=schema_meta(
            schema={
                "type": "string",
                "minLength": 1,
                "description": "输出文件路径(相对路径以进程CWD为基准;自动mkdir父目录)",
                "markdownDescription": (
                    "输出文件路径.\n\n"
                    "- 相对路径以运行时进程当前工作目录(CWD)为基准(不是 YAML 文件所在目录)\n"
                    "- 会自动创建父目录: `mkdir(parents=True, exist_ok=True)`\n"
                    "- 可能覆盖同名文件\n"
                    "- 安全提示: 该路径完全由配置控制, 不要对不可信 YAML 开启文件输出"
                ),
                "examples": ["./output/report.xlsx", "./output/report.csv"],
            }
        ),
    )
    """输出文件路径."""

    sheet: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "type": "string",
                "minLength": 1,
                "description": "Excel sheet 名称(仅 workbook)",
                "markdownDescription": "Excel sheet 名称(仅 `type: workbook`).",
                "examples": ["订单明细", "Summary"],
            }
        ),
    )
    """可选:工作表名称(仅 `workbook`)."""

    encoding: str = dataclass_field(
        default=DEFAULT_OUTPUT_ENCODING,
        metadata=schema_meta(
            desc="文件编码(CSV 输出使用)",
            md="文件编码(CSV 输出使用).",
            default=DEFAULT_OUTPUT_ENCODING,
            examples=[DEFAULT_OUTPUT_ENCODING],
        ),
    )
    """文件编码(CSV 输出使用)."""

    streaming: bool = dataclass_field(
        default=DEFAULT_OUTPUT_STREAMING,
        metadata=schema_meta(
            desc="启用流式输出(必须为 true)",
            md=("启用流式输出(按行写入).\n\n- composed outputs 仅支持 `true`"),
            default=DEFAULT_OUTPUT_STREAMING,
            examples=[True],
        ),
    )
    """是否启用流式写出(按行写入)."""

    include_header: bool = dataclass_field(
        default=DEFAULT_OUTPUT_INCLUDE_HEADER,
        metadata=schema_meta(
            desc="包含表头行",
            md="包含表头行.",
            default=DEFAULT_OUTPUT_INCLUDE_HEADER,
            examples=[True],
        ),
    )
    """是否包含表头行."""

    header_fields_output_by: str = dataclass_field(
        default=DEFAULT_OUTPUT_HEADER_BY,
        metadata=schema_meta(
            desc="表头字段名来源: field_id/name",
            md=("表头字段名来源.\n\n- `field_id`: 使用字段 ID\n- `name`: 使用字段的 `name`(为空或等于 field_id 时回退为 field_id)"),
            choices=["field_id", "name"],
            default=DEFAULT_OUTPUT_HEADER_BY,
            examples=["field_id"],
        ),
    )
    """表头字段名来源."""

    allow_formulas: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="允许 Excel 公式(仅 workbook)",
            md="允许 Excel 公式(仅 `type: workbook`).",
            default=False,
            examples=[False],
        ),
    )
    """是否允许 `Excel` 公式(仅 `workbook`)."""

    write_lock: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="写锁(仅 workbook)",
            md="写锁(仅 `type: workbook`; 多目标共享同一 workbook 时建议开启).",
            default=False,
            examples=[True],
        ),
    )
    """是否启用 `Excel` 写锁(仅 `workbook`)."""


@dataclass(frozen=True)
class OutputAggregateFieldConfig:
    """`aggregate.fields.<out_field_id>` 的单字段配置(已解析).

    说明:
    - `producer_key`: 生产该字段的函数键(例如 `sum`/`dense_rank`/`call_by`).
    - `config`: 对应该 `producer_key` 的配置对象(`dict` 或 `str`).
    """

    producer_key: str
    config: Any
    name: str = ""


@dataclass(frozen=True)
class OutputAggregateConfig:
    SCHEMA_NAME: ClassVar[str] = "output_aggregate"
    """派生汇总配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("group_by", "fields")
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    group_by: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            schema={
                "type": "array",
                "minItems": 1,
                "items": {
                    "anyOf": [
                        FIELD_ID_STRING_SCHEMA,
                        {"type": "object"},
                        {
                            "type": "array",
                            "items": {"anyOf": [FIELD_ID_STRING_SCHEMA, {"type": "object"}]},
                            "minItems": 1,
                        },
                    ]
                },
            },
            desc="分组字段列表",
            md=(
                "分组字段列表(`field_id` 列表; 支持 YAML alias).\n\n"
                "支持两种等价写法:\n\n"
                "1) 直接写 `field_id` 字符串:\n\n"
                "```yaml\n"
                "group_by: [cs_id, cs_name]\n"
                "```\n\n"
                "2) 使用 YAML alias 引用字段定义对象以推导 `field_id`:\n\n"
                "```yaml\n"
                "main_source:\n"
                "  fields:\n"
                "    cs_id: &cs_id {extract: cs_id}\n"
                "outputs:\n"
                "  - name: by_cs\n"
                "    aggregate:\n"
                "      group_by:\n"
                "        - *cs_id\n"
                "```\n\n"
                "注意: YAML merge(`<<`) 可能产生新对象并丢失 alias identity;此时建议直接使用字符串 `field_id`.\n\n"
                "- `group_by` 引用的是输入行字段(`field_id`),来自 `where` 过滤后的行流\n"
                "- 每个唯一的 group key 组合会产生 1 行聚合输出\n"
                "- `partition_by`(排名分区)要求为 `group_by` 子集,用于保证聚合输出可解释性"
            ),
            examples=[["cs_id", "cs_name"]],
        ),
    )
    """分组字段列表."""

    fields: Dict[str, OutputAggregateFieldConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            schema={
                "type": "object",
                "minProperties": 1,
                "propertyNames": FIELD_ID_STRING_SCHEMA,
                "additionalProperties": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["count"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "count": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "可选:输入字段(field_id);提供时统计非空值个数",
                                            "markdownDescription": "可选:输入字段(`field_id`);提供时统计非空值个数.",
                                            "examples": ["order_id"],
                                        }
                                    },
                                    "description": "count: 行数(或非空值数)",
                                    "markdownDescription": (
                                        "行数/计数指标.\n\n"
                                        "- `count: {}`: 统计组内行数\n"
                                        "- `count: {field: <field_id>}`: 统计组内该字段非空值个数\n\n"
                                        "执行阶段: 聚合指标(先于排名/派生字段)."
                                    ),
                                    "examples": [{}, {"field": "order_id"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["sum"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "sum": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["field"],
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "输入字段(field_id)",
                                            "markdownDescription": "输入字段(`field_id`).",
                                            "examples": ["amount_yuan"],
                                        }
                                    },
                                    "description": "sum: 数值求和",
                                    "markdownDescription": (
                                        "数值求和指标.\n\n"
                                        "- 跳过 `None`\n"
                                        "- 对非数值输入尽量做安全转换(失败则跳过)\n\n"
                                        "参数:\n- `field`: 输入字段(`field_id`)."
                                    ),
                                    "examples": [{"field": "amount_yuan"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["min"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "min": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["field"],
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "输入字段(field_id)",
                                            "markdownDescription": "输入字段(`field_id`).",
                                            "examples": ["amount_yuan"],
                                        }
                                    },
                                    "description": "min: 最小值",
                                    "markdownDescription": "最小值指标.\n\n参数:\n- `field`: 输入字段(`field_id`).",
                                    "examples": [{"field": "amount_yuan"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["max"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "max": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["field"],
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "输入字段(field_id)",
                                            "markdownDescription": "输入字段(`field_id`).",
                                            "examples": ["amount_yuan"],
                                        }
                                    },
                                    "description": "max: 最大值",
                                    "markdownDescription": "最大值指标.\n\n参数:\n- `field`: 输入字段(`field_id`).",
                                    "examples": [{"field": "amount_yuan"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["count_true"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "count_true": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["field"],
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "输入字段(field_id)",
                                            "markdownDescription": "输入字段(`field_id`).",
                                            "examples": ["is_paid"],
                                        }
                                    },
                                    "description": "count_true: 统计 truthy 行数",
                                    "markdownDescription": ("统计组内某字段为 truthy 的行数.\n\n参数:\n- `field`: 输入字段(`field_id`)."),
                                    "examples": [{"field": "is_paid"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["count_true_gte"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "count_true_gte": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["field", "threshold"],
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "输入字段(field_id)",
                                            "markdownDescription": "输入字段(`field_id`).",
                                            "examples": ["amount_yuan"],
                                        },
                                        "threshold": {
                                            "description": "阈值(>= threshold 为 true)",
                                            "markdownDescription": "阈值(>= threshold 为 true).",
                                            "examples": [0, 100, 99.5],
                                        },
                                    },
                                    "description": "count_true_gte: 统计数值 >= 阈值的行数",
                                    "markdownDescription": (
                                        "统计组内某字段数值 >= 阈值的行数.\n\n参数:\n- `field`: 输入字段(`field_id`).\n- `threshold`: 阈值."
                                    ),
                                    "examples": [{"field": "amount_yuan", "threshold": 100}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["count_distinct"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "count_distinct": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "oneOf": [
                                        {
                                            "required": ["field"],
                                            "not": {"required": ["fields"]},
                                        },
                                        {
                                            "required": ["fields"],
                                            "not": {"required": ["field"]},
                                        },
                                    ],
                                    "properties": {
                                        "field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "输入字段(field_id)",
                                            "markdownDescription": "输入字段(`field_id`).",
                                            "examples": ["user_id"],
                                        },
                                        "fields": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "复合去重键(字段列表)",
                                            "markdownDescription": "复合去重键(`field_id` 列表).",
                                            "examples": [["user_id", "item_id"]],
                                        },
                                    },
                                    "description": "count_distinct: 去重计数",
                                    "markdownDescription": (
                                        "去重计数指标.\n\n"
                                        "- 支持单字段去重: `field`\n"
                                        "- 支持复合键去重: `fields`\n"
                                        "- 去重护栏由 `max_distinct`/`distinct_on_overflow` 控制\n\n"
                                        "约束:\n- 必须且只能提供 `field` 或 `fields` 之一."
                                    ),
                                    "examples": [{"field": "user_id"}, {"fields": ["user_id", "item_id"]}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["row_number"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "row_number": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["by"],
                                    "properties": {
                                        "by": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "用于排序的字段(引用 group_by 或 aggregate.fields 任意字段,含派生字段)",
                                            "markdownDescription": (
                                                "用于排序的字段(引用 `group_by` 或 `aggregate.fields` 任意字段,含派生字段)."
                                            ),
                                            "examples": ["sum_amount"],
                                        },
                                        "partition_by": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "可选:排名分区字段列表(必须是 group_by 子集)",
                                            "markdownDescription": "可选:排名分区字段列表(必须是 `group_by` 子集).",
                                            "examples": [["region_id"]],
                                        },
                                        "order": {
                                            "type": "string",
                                            "enum": ["asc", "desc"],
                                            "default": "desc",
                                            "description": "排序方向(asc/desc)",
                                            "markdownDescription": "排序方向.\n\n- `asc`: 升序\n- `desc`: 降序",
                                            "examples": ["desc"],
                                        },
                                        "order_by": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "可选:稳定排序字段列表(用于 tie-break; top_k_mode=rows 必填)",
                                            "markdownDescription": (
                                                "可选:稳定排序字段列表.\n\n"
                                                "- 用于输出稳定排序与 `top_k_mode=rows` 的稳定 tie-break\n"
                                                "- 缺省时等价于 `[by]`"
                                            ),
                                            "examples": [["sum_amount", "cs_id"]],
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "minimum": 0,
                                            "default": 0,
                                            "description": "可选:每个分区保留前 K 个(0 表示不限制)",
                                            "markdownDescription": "可选:每个分区保留前 K 个(0 表示不限制).",
                                            "examples": [0, 100],
                                        },
                                        "top_k_mode": {
                                            "type": "string",
                                            "enum": ["rank", "rows"],
                                            "default": "rank",
                                            "description": "top_k 模式(rank=含并列扩张; rows=固定 K 行)",
                                            "markdownDescription": (
                                                "top_k 模式.\n\n"
                                                "- `rank`(默认): 保留 `rank_value <= K` 的所有行(含并列扩张)\n"
                                                "- `rows`: 强行取前 K 行(允许截断并列);为保证确定性,必须提供 `order_by`"
                                            ),
                                            "examples": ["rank"],
                                        },
                                    },
                                    "description": "row_number: 连续序号(不合并并列)",
                                    "markdownDescription": (
                                        "连续序号(1..N),不合并并列.\n\n"
                                        "- `by`: 用于排序(并列不合并)\n"
                                        "- `partition_by`: 分区内重置序号(必须是 `group_by` 子集)\n\n"
                                        "执行阶段: 排名字段(在聚合指标之后)."
                                    ),
                                    "examples": [{"by": "sum_amount", "order": "desc"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["rank"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "rank": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["by"],
                                    "properties": {
                                        "by": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": (
                                                "用于计算 rank 值与并列判断的字段(引用 group_by 或 aggregate.fields 任意字段,含派生字段)"
                                            ),
                                            "markdownDescription": (
                                                "用于计算 rank 值与并列判断的字段(引用 `group_by` 或 `aggregate.fields` 任意字段,"
                                                "含派生字段)."
                                            ),
                                            "examples": ["sum_amount"],
                                        },
                                        "partition_by": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "可选:排名分区字段列表(必须是 group_by 子集)",
                                            "markdownDescription": "可选:排名分区字段列表(必须是 `group_by` 子集).",
                                            "examples": [["region_id"]],
                                        },
                                        "order": {
                                            "type": "string",
                                            "enum": ["asc", "desc"],
                                            "default": "desc",
                                            "description": "排序方向(asc/desc)",
                                            "markdownDescription": "排序方向.\n\n- `asc`: 升序\n- `desc`: 降序",
                                            "examples": ["desc"],
                                        },
                                        "order_by": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "可选:稳定排序字段列表(用于 tie-break; top_k_mode=rows 必填)",
                                            "markdownDescription": (
                                                "可选:稳定排序字段列表.\n\n"
                                                "- 用于输出稳定排序与 `top_k_mode=rows` 的稳定 tie-break\n"
                                                "- 缺省时等价于 `[by]`"
                                            ),
                                            "examples": [["sum_amount", "cs_id"]],
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "minimum": 0,
                                            "default": 0,
                                            "description": "可选:每个分区保留前 K 个(0 表示不限制)",
                                            "markdownDescription": "可选:每个分区保留前 K 个(0 表示不限制).",
                                            "examples": [0, 100],
                                        },
                                        "top_k_mode": {
                                            "type": "string",
                                            "enum": ["rank", "rows"],
                                            "default": "rank",
                                            "description": "top_k 模式(rank=含并列扩张; rows=固定 K 行)",
                                            "markdownDescription": (
                                                "top_k 模式.\n\n"
                                                "- `rank`(默认): 保留 `rank_value <= K` 的所有行(含并列扩张)\n"
                                                "- `rows`: 强行取前 K 行(允许截断并列);为保证确定性,必须提供 `order_by`"
                                            ),
                                            "examples": ["rank"],
                                        },
                                    },
                                    "description": "rank: SQL rank(并列共享名次,后续跳号)",
                                    "markdownDescription": (
                                        "SQL `rank` 语义: (1,1,3...).\n\n"
                                        "- 并列判断只由 `by` 的值决定(不要用 `order_by` 打散并列)\n"
                                        "- `order_by` 仅用于输出稳定排序与 `top_k_mode=rows` 的确定性 tie-break\n\n"
                                        "执行阶段: 排名字段(在聚合指标之后)."
                                    ),
                                    "examples": [{"by": "sum_amount", "order": "desc"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["dense_rank"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "dense_rank": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["by"],
                                    "properties": {
                                        "by": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": (
                                                "用于计算 rank 值与并列判断的字段(引用 group_by 或 aggregate.fields 任意字段,含派生字段)"
                                            ),
                                            "markdownDescription": (
                                                "用于计算 rank 值与并列判断的字段(引用 `group_by` 或 `aggregate.fields` 任意字段,"
                                                "含派生字段)."
                                            ),
                                            "examples": ["sum_amount"],
                                        },
                                        "partition_by": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "可选:排名分区字段列表(必须是 group_by 子集)",
                                            "markdownDescription": "可选:排名分区字段列表(必须是 `group_by` 子集).",
                                            "examples": [["region_id"]],
                                        },
                                        "order": {
                                            "type": "string",
                                            "enum": ["asc", "desc"],
                                            "default": "desc",
                                            "description": "排序方向(asc/desc)",
                                            "markdownDescription": "排序方向.\n\n- `asc`: 升序\n- `desc`: 降序",
                                            "examples": ["desc"],
                                        },
                                        "order_by": {
                                            "type": "array",
                                            "items": _FIELD_REF_LIST_ITEM_SCHEMA,
                                            "minItems": 1,
                                            "description": "可选:稳定排序字段列表(用于 tie-break; top_k_mode=rows 必填)",
                                            "markdownDescription": (
                                                "可选:稳定排序字段列表.\n\n"
                                                "- 用于输出稳定排序与 `top_k_mode=rows` 的稳定 tie-break\n"
                                                "- 缺省时等价于 `[by]`"
                                            ),
                                            "examples": [["sum_amount", "cs_id"]],
                                        },
                                        "top_k": {
                                            "type": "integer",
                                            "minimum": 0,
                                            "default": 0,
                                            "description": "可选:每个分区保留前 K 个(0 表示不限制)",
                                            "markdownDescription": "可选:每个分区保留前 K 个(0 表示不限制).",
                                            "examples": [0, 100],
                                        },
                                        "top_k_mode": {
                                            "type": "string",
                                            "enum": ["rank", "rows"],
                                            "default": "rank",
                                            "description": "top_k 模式(rank=含并列扩张; rows=固定 K 行)",
                                            "markdownDescription": (
                                                "top_k 模式.\n\n"
                                                "- `rank`(默认): 保留 `rank_value <= K` 的所有行(含并列扩张)\n"
                                                "- `rows`: 强行取前 K 行(允许截断并列);为保证确定性,必须提供 `order_by`"
                                            ),
                                            "examples": ["rank"],
                                        },
                                    },
                                    "description": "dense_rank: SQL dense_rank(并列共享名次,后续不跳号)",
                                    "markdownDescription": (
                                        "SQL `dense_rank` 语义: (1,1,2...).\n\n"
                                        "- 并列判断只由 `by` 的值决定(不要用 `order_by` 打散并列)\n"
                                        "- `order_by` 仅用于输出稳定排序与 `top_k_mode=rows` 的确定性 tie-break\n\n"
                                        "执行阶段: 排名字段(在聚合指标之后)."
                                    ),
                                    "examples": [{"by": "sum_amount", "order": "desc"}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["score_by_rank"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "score_by_rank": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "rank_field": {
                                            **_FIELD_REF_OR_ALIAS_SCHEMA,
                                            "description": "可选:引用的排名字段(out_field_id);缺省为 'rank'",
                                            "markdownDescription": "可选:引用的排名字段(out_field_id);缺省为 `rank`.",
                                            "examples": ["rank"],
                                        },
                                        "base": {
                                            "description": "可选:基础分数(base)",
                                            "markdownDescription": "可选:基础分数(base).",
                                            "examples": [100],
                                        },
                                        "step": {
                                            "description": "可选:每名次衰减(step)",
                                            "markdownDescription": "可选:每名次衰减(step).",
                                            "examples": [3],
                                        },
                                    },
                                    "description": "score_by_rank: 基于 rank 计算 score",
                                    "markdownDescription": (
                                        "基于排名字段计算 score(聚合后派生字段).\n\n"
                                        "默认公式:\n"
                                        "- `score = base - (rank - 1) * step`\n\n"
                                        "参数:\n"
                                        "- `rank_field`: 引用的排名字段(out_field_id),缺省为 `rank`\n"
                                        "- `base`: 基础分数(缺省 0)\n"
                                        "- `step`: 每名次衰减(缺省 1)\n\n"
                                        "执行语义: 聚合后派生字段 DAG 的一个节点(按依赖驱动在 finalize 阶段计算)."
                                    ),
                                    "examples": [{"rank_field": "rank", "base": 100, "step": 3}],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["call_by"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "call_by": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "call_by: 聚合后派生字段的 hotfix 口子(安全引用,受 allowlist 约束)",
                                    "markdownDescription": (
                                        "聚合后派生字段的 hotfix 口子(受 allowlist 约束).\n\n"
                                        "- 与 `compute` 一样属于聚合后派生字段,会与 rank/其它派生字段一起组成 DAG\n"
                                        "- 只可引用聚合输出行内字段: `group_by` + `aggregate.fields` 中声明的字段(含派生字段)\n"
                                        "- 不可引用明细行字段(聚合前状态不可用)\n"
                                        "- 若存在循环依赖,编译期会报错并给出依赖链路\n\n"
                                        "示例:\n"
                                        "```yaml\n"
                                        'score: {call_by: "pkg.mod:fn(rank=rank, base=100, step=3)"}\n'
                                        "```"
                                    ),
                                    "examples": ["pkg.mod:fn(rank=rank, base=100, step=3)"],
                                },
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["compute"],
                            "properties": {
                                **_AGG_OUT_FIELD_NAME_SCHEMA,
                                "compute": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "compute: 聚合后派生字段安全表达式(推荐)",
                                    "markdownDescription": (
                                        "安全表达式派生字段(推荐).\n\n"
                                        "- 语法与 `fields.*.compute` / `where` 一致\n"
                                        "- 变量名为聚合输出行字段 ID: `group_by` + `aggregate.fields` 中声明的字段(含派生字段)\n"
                                        "- 会参与 aggregate DAG: 按依赖驱动计算; 循环依赖会在编译期报错\n"
                                        "- 适合 ratio/求和/加权等简单派生; 复杂逻辑可用 `call_by`(仍受 allowlist 约束)"
                                    ),
                                    "examples": ["sum_a / sum_b", "score1 + score2"],
                                },
                            },
                        },
                    ]
                },
            },
            desc="聚合输出字段映射(key 为 out_field_id)",
            md=(
                "聚合输出字段映射(key 为 out_field_id).\n\n"
                "- map key 是输出字段 ID\n"
                "- map value 是“该字段如何产生”的声明,必须且只能选择一个 producer key\n"
                "- producer key 分三类:\n"
                "  1) 聚合指标函数(例如 `count`/`sum`/`count_distinct`)\n"
                "  2) 排名函数(例如 `row_number`/`rank`/`dense_rank`)\n"
                "  3) 聚合后派生字段(例如 `compute`/`score_by_rank`/`call_by`)\n\n"
                "执行顺序/语义(依赖驱动 DAG):\n"
                "- `rank` + 聚合后派生字段统一视为同一套 DAG,在 finalize 阶段按拓扑序执行\n"
                "- 引用范围: `group_by` + `aggregate.fields` 任意 out_field_id(含派生字段)\n"
                "- 系统会在编译期构建依赖图,检测循环依赖并给出依赖链路\n"
                "- `top_k/sort` 会在计算完所有 rank 字段及其上游依赖后执行; 其余派生字段可在过滤后计算\n\n"
                "边界:\n"
                "- 不可引用明细行字段(除 `group_by`);聚合前中间状态不会被保留"
            ),
        ),
    )
    """聚合输出字段映射."""

    max_groups: int = dataclass_field(
        default=0,
        metadata=schema_meta(
            desc="max_groups 护栏(0 表示不限制)",
            md="max_groups 护栏(0 表示不限制).",
            min=0,
            default=0,
            examples=[0, 10000],
        ),
    )
    """可选:聚合分组数护栏(0 表示不限制)."""

    max_distinct: int = dataclass_field(
        default=0,
        metadata=schema_meta(
            desc="max_distinct 护栏(0 表示不限制)",
            md="max_distinct 护栏(0 表示不限制).",
            min=0,
            default=0,
            examples=[0, 200000],
        ),
    )
    """可选:去重护栏(0 表示不限制)."""

    distinct_on_overflow: str = dataclass_field(
        default="error",
        metadata=schema_meta(
            desc="distinct 护栏溢出策略(error/truncate)",
            md="distinct 护栏溢出策略.\n\n- `error`: 失败\n- `truncate`: 截断并继续",
            choices=["error", "truncate"],
            default="error",
            examples=["error"],
        ),
    )
    """去重护栏溢出策略."""


@dataclass(frozen=True)
class OutputTargetConfig:
    SCHEMA_NAME: ClassVar[str] = "output_target"
    """输出目标配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("name",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    name: str = dataclass_field(
        default="",
        metadata=schema_meta(schema=_OUTPUT_NAME_SCHEMA, desc="输出名称(name)"),
    )
    """输出名称(`name`; 必填且唯一)."""

    from_: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=_OUTPUT_NAME_SCHEMA,
            schema_name="from",
            desc="可选:继承来源输出(name)",
            md=("可选:继承来源输出(name).\n\n- 继承字段集合与容器配置\n- 不继承 where/aggregate"),
            examples=["detail"],
        ),
    )
    """可选:继承来源输出."""

    container: Optional[OutputContainerConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            ref="output_container",
            desc="输出容器配置(workbook/csv)",
        ),
    )
    """可选:输出容器配置(允许通过 `from` 继承)."""

    fields: Optional[Tuple[str, ...]] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "type": "array",
                "items": {
                    "anyOf": [
                        FIELD_ID_STRING_SCHEMA,
                        {"type": "object"},
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    FIELD_ID_STRING_SCHEMA,
                                    {"type": "object"},
                                ]
                            },
                            "minItems": 1,
                        },
                    ]
                },
                "minItems": 1,
            },
            desc="输出字段顺序(field_id/out_field_id 列表; 支持 YAML alias)",
            md=(
                "输出字段顺序(`field_id/out_field_id` 列表).\n\n"
                "两类输出的语义:\n\n"
                "- 明细输出(未声明 `aggregate`): `fields` **必填**,用于选择并编排行输出字段.\n"
                "- 聚合输出(声明了 `aggregate`): `fields` **可选**,用于 derived output 的输出编排(select + order).\n"
                "  - 可引用范围: `aggregate.group_by` + `aggregate.fields` 的 key\n"
                "  - 若省略 `fields`,则使用默认 derived output layout(实现细节;不承诺顺序,强合同请显式声明)\n\n"
                "支持两种等价写法:\n\n"
                "1) 直接写 `field_id` 字符串:\n\n"
                "```yaml\n"
                "fields: [order_id, total]\n"
                "```\n\n"
                "2) 使用 YAML alias 引用字段定义对象以推导 `field_id`:\n\n"
                "```yaml\n"
                "main_source:\n"
                "  fields:\n"
                "    quantity: &quantity {extract: quantity}\n"
                "outputs:\n"
                "  - name: detail\n"
                "    container: {type: csv, path: ./out.csv}\n"
                "    fields:\n"
                "      - *quantity\n"
                '      - "order_id"\n'
                "```\n\n"
                "注意: YAML merge(`<<`) 可能产生新对象并丢失 alias identity;此时建议直接使用字符串 `field_id`.\n\n"
                "可通过 `from` 继承."
            ),
            examples=[["order_id", "user_id"]],
        ),
    )
    """可选:输出字段顺序(`field_id` 列表)."""

    where: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:过滤表达式(安全表达式)",
            md=(
                "可选:行级过滤谓词(安全表达式),等价 SQL `WHERE`.\n\n"
                "执行阶段:\n"
                "- 明细输出: 写出前对每行执行,命中才写入该 output\n"
                "- 聚合输出: `group_by` 之前对每行执行,只有命中的行参与聚合\n\n"
                "变量来源:\n"
                "- 表达式可引用当前行的字段值,来自 demand 的 `fields.<field_id>`(包含 relation/derived 后的字段)\n"
                "- 系统会在编译期静态提取表达式依赖字段并注入 required fields\n"
                "- 只保证表达式引用到的字段会被准备;未引用字段可能为 `None`\n\n"
                "限制:\n"
                "- 仅支持受限表达式(禁止任意 import)\n"
                "- `where` 是按行过滤/路由,不是“是否启用 sheet/output”的开关;该能力应由未来独立字段提供(例如 `enabled_if`)\n"
                "- `where` 不能引用聚合后输出字段(例如 `aggregate.fields.*` 产生的指标/排名/派生字段)"
            ),
            examples=["channel == 'direct'"],
        ),
    )
    """可选:过滤表达式(安全表达式)."""

    aggregate: Optional[OutputAggregateConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            ref="output_aggregate",
            desc="可选:派生汇总配置(声明后视为 derived output)",
        ),
    )
    """可选:派生汇总配置(声明后视为派生输出)."""

    requires: Tuple[str, ...] = dataclass_field(default_factory=tuple, metadata=schema_omit())
    """编译期注入: `where` 等表达式依赖字段(内部字段)."""


@dataclass(frozen=True)
class OutputExtraSheetConfig:
    SCHEMA_NAME: ClassVar[str] = "output_extra_sheet"
    """额外工作表(`meta`/`audit`)配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    path: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:工作簿路径(缺省使用 primary workbook)",
            md="可选:工作簿路径(缺省使用 primary workbook).",
            examples=["./output/report.xlsx"],
        ),
    )
    """可选:工作簿路径(缺省使用 `primary` 输出的工作簿)."""

    sheet: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "type": "string",
                "minLength": 1,
                "description": "sheet 名称",
                "markdownDescription": "sheet 名称.",
                "examples": ["__meta__", "__audit__"],
            }
        ),
    )
    """可选:工作表名称."""

    allow_formulas: Optional[bool] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:允许 Excel 公式(缺省使用 primary workbook 的容器配置)",
            md="可选:允许 Excel 公式(缺省使用 primary workbook 的容器配置).",
            examples=[False],
        ),
    )
    """可选:允许 `Excel` 公式."""

    write_lock: Optional[bool] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:写锁(缺省使用 primary workbook 的容器配置)",
            md="可选:写锁(缺省使用 primary workbook 的容器配置).",
            examples=[True],
        ),
    )
    """可选:写锁."""
