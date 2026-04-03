from typing import ClassVar, Dict, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import (
    DEFAULT_BATCH_SIZE,
    DESC_MAIN_SOURCE,
    DESC_MAIN_SOURCE_MD,
    SOURCE_ID_STRING_SCHEMA,
    schema_meta,
    schema_omit,
    schema_ref,
)
from .field import DerivedFieldConfig, SourceFieldConfig
from .guardrails import GuardrailsConfig
from .lookup_bind_relation import RelationConfig
from .outputs import OutputExtraSheetConfig, OutputTargetConfig
from .resources import ResourcesConfig
from .source import LoaderRetryConfig, MainSourceConfig, SourceConfig


@dataclass(frozen=True)
class DemandConfig:
    SCHEMA_NAME: ClassVar[str] = "demand"
    """配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    name: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="需求配置名称",
            md="需求配置名称.\n\n- 必填, 用于标识当前配置",
            examples=["order_report"],
        ),
    )
    """需求配置名称,用于标识当前需求."""

    description: str = dataclass_field(default="", metadata=schema_meta(desc="配置描述", md="配置描述(可选)."))
    """配置说明(可选)."""

    batch_size: Optional[int] = dataclass_field(
        default=DEFAULT_BATCH_SIZE,
        metadata=schema_omit(),
    )
    """运行期批处理大小;从 `YAML` 主线迁出,通过运行入口参数控制."""

    retry: Optional[LoaderRetryConfig] = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )
    """运行期加载重试配置;从 `YAML` 主线迁出,通过运行入口参数控制."""

    main_source: MainSourceConfig = dataclass_field(
        default_factory=MainSourceConfig,
        metadata=schema_meta(desc=DESC_MAIN_SOURCE, md=DESC_MAIN_SOURCE_MD, ref="main_source"),
    )
    """主数据源配置."""

    sources: Dict[str, SourceConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="数据源配置映射, key 为 source_id",
            md=(
                "数据源配置映射, key 为 `source_id`.\n\n"
                "- 每个 source 必填: `loader`, `key`\n"
                "- 不允许包含 `main_source.source_id`\n"
                "- `fields` 仅允许源字段(禁止 `compute`)"
            ),
            propertyNames={"anyOf": [{"const": "$import"}, SOURCE_ID_STRING_SCHEMA]},
            additional_props=schema_ref("source"),
            min_props=0,
        ),
    )
    """额外数据源配置映射,键为 `source_id`."""

    source_fields: Dict[str, SourceFieldConfig] = dataclass_field(default_factory=dict, metadata=schema_omit())
    """解析后汇总的源字段配置映射(内部字段)."""

    derived_fields: Dict[str, DerivedFieldConfig] = dataclass_field(default_factory=dict, metadata=schema_omit())
    """解析后汇总的派生字段配置映射(内部字段)."""

    source_field_id_map: Dict[str, Dict[str, str]] = dataclass_field(default_factory=dict, metadata=schema_omit())
    """按数据源分组的字段标识映射(内部字段)."""

    relations: Dict[str, RelationConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="命名关联关系映射(steps 模板),供字段通过 string ref/alias 复用",
            md=(
                "命名关联关系映射(steps 模板).\n\n"
                "- 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用\n"
                "- string ref: `relation: <relation_id>` 引用 `relations.<relation_id>`\n"
                "- alias 复用: `relation: *<anchor>` (YAML anchor)\n"
                "- steps 必须是等值关联链, 参考 `relation.steps`"
            ),
            additional_props=schema_ref("relation"),
        ),
    )
    """命名关联关系映射,供字段通过别名复用."""

    guardrails: Optional[GuardrailsConfig] = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )
    """运行期护栏配置;从 `YAML` 主线迁出,通过运行入口参数控制."""

    resources: Optional[ResourcesConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            ref="resources",
            desc="可选:IO 资源声明(resources.*)",
            md="可选:IO 资源声明.\n\n- 稳定入口: `resources.books` / `resources.files`",
        ),
    )
    """可选:`IO` 资源声明."""

    outputs: Tuple[OutputTargetConfig, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="输出目标列表(多 sheet 分发 + 派生汇总; 可选)",
            md=(
                "输出目标列表(有序; 可选).\n\n"
                "- 顶层 `outputs` 可省略,用于保持 demand YAML 可复用(通常仅承载需求本体)\n"
                "- 需要运行时动态指定输出(字段/路径/sheet/header 策略)时,推荐在 Python 调用侧使用与 YAML 同形的 `overrides.outputs`\n"
                "- 通过 `where` 分发到不同 sheet\n"
                "- 通过 `aggregate` 声明派生汇总输出\n"
                "- 通过 `from` 复用字段集合与容器配置\n"
                "- 不再支持旧写法: 顶层 `output:`"
            ),
            min_items=0,
            examples=[
                [
                    {
                        "name": "detail",
                        "to": {"sheet": "明细"},
                        "fields": ["order_id", "user_id"],
                    }
                ]
            ],
        ),
    )
    """输出目标列表(有序)."""

    validate_unique_field_names: bool = dataclass_field(
        default=True,
        metadata=schema_omit(),
    )
    """运行期预检查:字段有效展示名(`effective display name`)全局唯一(从 `YAML` 主线迁出)."""

    failure_policy: str = dataclass_field(
        default="all_fail",
        metadata=schema_omit(),
    )
    """运行期多输出失败策略;从 `YAML` 主线迁出,通过运行入口参数控制."""

    include_full_error_message: bool = dataclass_field(
        default=False,
        metadata=schema_omit(),
    )
    """运行期诊断策略:是否包含完整错误信息(可能包含敏感信息;从 `YAML` 主线迁出)."""

    meta: Optional[OutputExtraSheetConfig] = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )
    """运行期输出附加工作表:`meta`;从 `YAML` 主线迁出,通过运行入口参数控制."""

    audit: Optional[OutputExtraSheetConfig] = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )
    """运行期输出附加工作表:`audit`;从 `YAML` 主线迁出,通过运行入口参数控制."""


__all__ = ()
