from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ..constants import (
    DEFAULT_OUTPUT_ENCODING,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_HEADER_BY,
    DEFAULT_OUTPUT_INCLUDE_HEADER,
    DEFAULT_OUTPUT_STREAMING,
    DESC_FIELD_NAME,
    DESC_FIELD_NAME_MD,
    OUTPUT_FIELD_ID_KEY,
    RELATION_STEPS_SCHEMA,
    SOURCE_ID_STRING_SCHEMA,
    VALUE_CAST_ENUM,
    schema_meta,
    schema_omit,
)
from ..doc_texts import SOURCE_FIELD_EXTRACT_DESC, SOURCE_FIELD_EXTRACT_MD
from .lookup_bind_relation import InlineRelationConfig


@dataclass(frozen=True)
class SourceFieldConfig:
    SCHEMA_NAME: ClassVar[str] = "source_field"
    """源字段配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ALL_OF: ClassVar[List[Dict[str, Any]]] = [
        {"not": {"required": ["call_by"]}},
        {"not": {"required": ["field"]}},
    ]
    """用于约束:源字段配置中禁止声明 `call_by` 与历史 `field`."""

    field_id: str = dataclass_field(default="", metadata=schema_omit())
    """字段标识(内部字段;由外层映射键提供)."""

    source: str = dataclass_field(
        default="",
        metadata=schema_meta(
            schema={
                **SOURCE_ID_STRING_SCHEMA,
                "description": "字段来源的 source_id (例: source: orders)",
                "markdownDescription": (
                    "字段来源的 `source_id`.\n\n"
                    "- 在 `main_source.fields` / `sources.<id>.fields` 中可省略\n"
                    "- 若显式提供, 必须与容器 `source_id` 一致"
                ),
            }
        ),
    )
    """字段来源的 `source_id`(可选;在容器内通常可省略)."""

    extract: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "type": "string",
                "minLength": 1,
                "description": SOURCE_FIELD_EXTRACT_DESC,
                "markdownDescription": SOURCE_FIELD_EXTRACT_MD,
                "examples": [
                    "review_status",
                    "CustomerMark.clearn_reason_level",
                    "[1].clearn_reason_level",
                    '["a.b"].x',
                ],
            }
        ),
    )
    """可选:字段提取表达式(缺省时等于字段键/`field_id`)."""

    name: str = dataclass_field(default="", metadata=schema_meta(desc=DESC_FIELD_NAME, md=DESC_FIELD_NAME_MD))
    """字段展示名称(可选)."""

    relation: Optional[InlineRelationConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "type": "object",
                "required": ["steps"],
                "properties": {"steps": RELATION_STEPS_SCHEMA},
                "additionalProperties": False,
                "description": "内联 steps 或 alias 引用(需先定义),示例: relation: {steps: [...]}",
                "markdownDescription": (
                    "关系路径引用(内联 steps 或 YAML alias; alias 需先在 relations 定义).\n\n"
                    "- `relation: *orders_to_customers`\n"
                    "- `relation: {steps: [...]}`\n"
                    "- steps 必须从 `main_source` 开始, 以当前 `source` 结束\n"
                    "- 不支持 relation_id 字符串\n"
                    "- 若 `source` 非 `main_source`, 且未显式 relation, 需确保 `relations` 中存在唯一链路"
                ),
            },
            desc=(
                "关系路径(仅 steps 对象或 YAML alias; alias 需先定义),"
                "表示从 main_source 到当前字段 source 的等值关联链 (例: relation: *orders_to_customers)"
            ),
        ),
    )
    """可选:关系路径引用(内联 `steps` 或 `YAML` 别名)."""

    value_cast: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="字段值转换(仅源字段),用于写入上下文/输出前的类型调整",
            md=("字段值转换(仅源字段).\n\n- `auto`: 自动转换\n- `int`: 转为 int\n- `str`: 转为 str"),
            choices=VALUE_CAST_ENUM,
            examples=["auto"],
        ),
    )
    """可选:字段值类型转换策略(仅源字段)."""


@dataclass(frozen=True)
class DerivedFieldConfig:
    SCHEMA_NAME: ClassVar[str] = "derived_field"
    """派生字段配置对象在 `YAML` 中的节点名称."""

    field_id: str = dataclass_field(default="", metadata=schema_omit())
    """字段标识(内部字段;由外层映射键提供)."""

    name: str = dataclass_field(default="", metadata=schema_meta(desc=DESC_FIELD_NAME, md=DESC_FIELD_NAME_MD))
    """字段展示名称(可选)."""

    compute: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="派生字段计算表达式(使用 field_id 作为变量名)",
            md=("派生字段计算表达式(与 `call_by` 互斥).\n\n- 使用 `field_id` 作为变量名\n- 必填, 不能为空"),
            examples=["revenue - cost"],
        ),
    )
    """派生字段计算表达式(与 `call_by` 互斥)."""

    call_by: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="派生字段函数调用(函数引用 + 参数列表),与 compute 互斥",
            md=(
                "派生字段函数调用(与 `compute` 互斥).\n\n"
                "- 语法: `reference(args...)`\n"
                "- `reference` 形式与 `loader` 引用一致,支持:\n"
                "  - 绝对引用: `module.path.function` / `module.path:function` / `module.path:obj.method`\n"
                "  - 相对引用: 以 `.` / `..` 开头的 module path(相对 YAML 文件所在目录)\n"
                "- 相对引用会在运行期先归一化为绝对引用,并继续受 allowlist(allowed_modules/allowed_functions) 约束\n"
                "- 支持位置参数与 kwargs\n"
                "- Python 字面量: `1`/`1.5`/`'ok'`/`True`/`False`/`None`\n"
                "- 上下文引用: `$ctx` 或 `$ctx.<attr>`\n"
                "- 可用 ctx 属性: `row_id`/`batch_num`/`field_id`/`deps`/`values`"
            ),
            examples=[
                "myapp.enums:get_status_text(status)",
                "myapp.enums:get_status_text(status=status, ctx=$ctx)",
                ".helpers:to_text(status)",
            ],
        ),
    )
    """派生字段函数调用(与 `compute` 互斥)."""

    depends_on: Tuple[str, ...] = dataclass_field(default_factory=tuple, metadata=schema_omit())
    """依赖字段标识列表(内部字段;解析后填充)."""


@dataclass(frozen=True)
class OutputConfig:
    SCHEMA_NAME: ClassVar[str] = "output"
    """输出配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    format: str = dataclass_field(
        default=DEFAULT_OUTPUT_FORMAT,
        metadata=schema_meta(
            desc="输出格式 (excel/csv)",
            md="输出格式.\n\n- `csv`: CSV 文件\n- `excel`: Excel 文件\n- 默认 `csv`",
            choices=["excel", "csv"],
            default=DEFAULT_OUTPUT_FORMAT,
            examples=["csv"],
        ),
    )
    """输出格式(例如 `excel`/`csv`)."""

    path: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="输出文件路径(相对路径以进程CWD为基准;自动mkdir父目录)",
            md=(
                "输出文件路径.\n\n"
                "- 为空则不生成文件\n"
                "- 相对路径以运行时进程当前工作目录(CWD)为基准(不是 YAML 文件所在目录)\n"
                "- 会自动创建父目录: `mkdir(parents=True, exist_ok=True)`\n"
                "- 可能覆盖同名文件\n"
                "- 注意: 该路径完全由配置控制, 不要对不可信 YAML 开启文件输出; 生产建议在受控工作目录/权限隔离环境运行"
            ),
        ),
    )
    """输出文件路径(为空则不生成文件)."""

    encoding: str = dataclass_field(
        default=DEFAULT_OUTPUT_ENCODING,
        metadata=schema_meta(desc="文件编码", md="文件编码(CSV 输出使用).", default=DEFAULT_OUTPUT_ENCODING),
    )
    """文件编码(用于 `CSV` 输出)."""

    streaming: bool = dataclass_field(
        default=DEFAULT_OUTPUT_STREAMING,
        metadata=schema_meta(
            desc="启用流式输出",
            md=(
                "启用流式输出(按行写入).\n\n"
                "- 推荐保持为 `true` 以降低内存占用(尤其是大批量 CSV/Excel 输出)\n"
                "- 设为 `false` 时会使用列式 file sink, 可能在 close() 前缓存大量输出数据"
            ),
            default=DEFAULT_OUTPUT_STREAMING,
        ),
    )
    """是否启用流式写出(按行写入)."""

    include_header: bool = dataclass_field(
        default=DEFAULT_OUTPUT_INCLUDE_HEADER,
        metadata=schema_meta(desc="包含表头行", md="包含表头行.", default=DEFAULT_OUTPUT_INCLUDE_HEADER),
    )
    """是否包含表头行."""

    header_fields_output_by: str = dataclass_field(
        default=DEFAULT_OUTPUT_HEADER_BY,
        metadata=schema_meta(
            desc="表头字段名来源: field_id=使用字段ID, name=使用字段的name属性",
            md=("表头字段名来源.\n\n- `field_id`: 使用字段 ID\n- `name`: 使用字段的 `name` (为空或等于 field_id 时回退为 field_id)"),
            choices=["field_id", "name"],
            default=DEFAULT_OUTPUT_HEADER_BY,
            examples=["field_id"],
        ),
    )
    """表头字段名来源:`field_id` 或 `name`."""

    fields: Optional[List[Any]] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="输出字段顺序(仅支持对象条目: 显式 {field_id: ...}/{field: ...} 或 YAML alias; 推荐显式对象)",
            md=(
                "输出字段顺序.\n\n"
                "推荐显式对象:\n- `{{{field_id_key}: order_id, name: 订单ID}}`\n\n"
                "按 data_key 选择:\n- `{{field: order_real_name, source: orders, name: 订单名}}`\n\n"
                "Alias 复用(指向已定义字段对象):\n- `*order_id`\n\n"
                "注意:\n"
                "- 每项必须是对象或 alias, 不支持纯字符串\n"
                "- 可用选择器: `field_id`(字段 ID) 或 `field`(loader data_key); 歧义时必须加 `source`\n"
                "- YAML merge(`<<`) 会生成新对象并丢失 alias 身份; merge 产物需包含 `field_id` 或 `field` 选择器\n"
                "- 显式对象除选择器键(`field_id`/`field`/`source`)外的键会覆盖字段配置"
            ).format(field_id_key=OUTPUT_FIELD_ID_KEY),
            items={"type": "object"},
        ),
    )
    """可选:输出字段顺序与字段覆盖配置列表."""
