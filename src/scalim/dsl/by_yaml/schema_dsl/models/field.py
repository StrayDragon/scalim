from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import (
    DESC_FIELD_NAME,
    DESC_FIELD_NAME_MD,
    FIELD_ID_STRING_SCHEMA,
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

    relation: Optional[Union[str, InlineRelationConfig]] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {
                        **FIELD_ID_STRING_SCHEMA,
                        "description": "relation 引用(字符串 ref),示例: relation: orders_to_customers",
                        "markdownDescription": (
                            "relation 引用(字符串 ref).\n\n"
                            "- 形式: `relation: <relation_id>`\n"
                            "- 表示引用 `relations.<relation_id>`\n"
                            "- full validate 会校验 `relations.<relation_id>` 存在"
                        ),
                    },
                    {
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
                            "- 若 `source` 非 `main_source`, 且未显式 relation, 需确保 `relations` 中存在唯一链路"
                        ),
                    },
                ]
            },
            desc=(
                "关系路径(支持 string ref / steps 对象 / YAML alias; alias 需先定义),"
                "表示从 main_source 到当前字段 source 的等值关联链 (例: relation: orders_to_customers)"
            ),
        ),
    )
    """可选:关系路径引用(内联 `steps` 或 `YAML` 别名)."""

    value_cast: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="字段值转换(仅源字段),用于写入上下文/输出前的类型调整",
            md=("字段值转换(仅源字段).\n\n- `auto`: 自动转换\n- `int`: 转为 int\n- `str`: 转为 str\n- `decimal`: 转为 Decimal"),
            choices=VALUE_CAST_ENUM,
            examples=["decimal"],
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
                "  - Python 引用(绝对/相对)\n"
                "  - 内置引用: `^<id>`\n"
                "- Python 相对引用会在运行期先归一化为绝对引用,并继续受 allowlist(allowed_modules/allowed_functions) 约束\n"
                "- `^<id>` 为受控词表(vocabulary)中的 builtin callable 引用,无需把目标模块加入 allowlist\n"
                "- 支持位置参数与 kwargs\n"
                "- Python 字面量: `1`/`1.5`/`'ok'`/`True`/`False`/`None`\n"
                "- 上下文引用: `$ctx` 或 `$ctx.<attr>`\n"
                "- 可用 ctx 属性: `row_id`/`batch_num`/`field_id`/`deps`/`values`"
            ),
            examples=[
                "myapp.enums:get_status_text(status)",
                "myapp.enums:get_status_text(status=status, ctx=$ctx)",
                ".helpers:to_text(status)",
                "^workflow/book_sheet_rows(ref)",
            ],
        ),
    )
    """派生字段函数调用(与 `compute` 互斥)."""

    depends_on: Tuple[str, ...] = dataclass_field(default_factory=tuple, metadata=schema_omit())
    """依赖字段标识列表(内部字段;解析后填充)."""


__all__ = []
