from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import ClassVar, Dict, Optional, Tuple

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
class OutputAggregateMetricConfig:
    SCHEMA_NAME: ClassVar[str] = "output_aggregate_metric"
    """派生汇总指标配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("op",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    op: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="聚合算子",
            md=("聚合算子.\n\n- `count`/`sum`/`min`/`max`\n- `count_true`/`count_true_gte`\n- `count_distinct`"),
            choices=["count", "sum", "min", "max", "count_true", "count_true_gte", "count_distinct"],
            examples=["count", "sum"],
        ),
    )
    """聚合算子."""

    field_id: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=FIELD_ID_STRING_SCHEMA,
            schema_name="field",
            desc="输入字段(field_id)",
            md="输入字段(field_id).",
            examples=["order_id", "amount_yuan"],
        ),
    )
    """可选:输入字段(`field_id`)."""

    field_ids: Optional[Tuple[str, ...]] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={"type": "array", "items": FIELD_ID_STRING_SCHEMA, "minItems": 1},
            schema_name="fields",
            desc="输入字段列表(field_id 列表)",
            md="输入字段列表(field_id 列表).",
            examples=[["user_id", "device_id"]],
        ),
    )
    """可选:输入字段列表(`field_id` 列表)."""

    threshold: Optional[object] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="阈值(部分算子需要)",
            md="阈值(部分算子需要;例如 `count_true_gte`).",
        ),
    )
    """可选:阈值(部分算子需要)."""


@dataclass(frozen=True)
class OutputAggregateConfig:
    SCHEMA_NAME: ClassVar[str] = "output_aggregate"
    """派生汇总配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("group_by", "metrics")
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    group_by: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            schema={"type": "array", "items": FIELD_ID_STRING_SCHEMA, "minItems": 1},
            desc="分组字段列表",
            md="分组字段列表(field_id 列表).",
            examples=[["cs_id", "cs_name"]],
        ),
    )
    """分组字段列表."""

    metrics: Dict[str, OutputAggregateMetricConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            schema={
                "type": "object",
                "minProperties": 1,
                "propertyNames": FIELD_ID_STRING_SCHEMA,
                "additionalProperties": {"$ref": "#/definitions/output_aggregate_metric"},
            },
            desc="聚合指标映射(key 为 out_field_id)",
            md="聚合指标映射(key 为 out_field_id).",
        ),
    )
    """聚合指标映射."""

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

    rank_by: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=FIELD_ID_STRING_SCHEMA,
            desc="可选:按某个输出字段排序生成 rank/top_k",
            md="可选:按某个输出字段排序生成 rank/top_k (字段为 out_field_id).",
            examples=["sum_amount"],
        ),
    )
    """可选:按某个输出字段排序生成 `rank`/`top_k`."""

    rank_field_id: str = dataclass_field(
        default="rank",
        metadata=schema_meta(
            desc="rank 输出字段名",
            md="rank 输出字段名.",
            default="rank",
            examples=["rank"],
        ),
    )
    """`rank` 输出字段名."""

    rank_order: str = dataclass_field(
        default="desc",
        metadata=schema_meta(
            desc="rank 排序方向(asc/desc)",
            md="rank 排序方向.\n\n- `asc`: 升序\n- `desc`: 降序",
            choices=["asc", "desc"],
            default="desc",
            examples=["desc"],
        ),
    )
    """`rank` 排序方向."""

    top_k: int = dataclass_field(
        default=0,
        metadata=schema_meta(
            desc="top_k 限制(0 表示不限制)",
            md="top_k 限制(0 表示不限制).",
            min=0,
            default=0,
            examples=[0, 100],
        ),
    )
    """`top_k` 限制(0 表示不限制)."""


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
            desc="明细输出字段顺序(field_id 列表; 支持 YAML alias)",
            md=(
                "明细输出字段顺序(`field_id` 列表).\n\n"
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
                "- 派生汇总输出(aggregate)不允许 fields\n"
                "- 可通过 `from` 继承"
            ),
            examples=[["order_id", "user_id"]],
        ),
    )
    """可选:明细输出字段顺序(`field_id` 列表)."""

    where: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:过滤表达式(安全表达式)",
            md=("可选:过滤表达式(安全表达式).\n\n- 仅支持受限表达式(禁止任意 import)\n- 编译期静态提取依赖字段并注入 required fields"),
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
