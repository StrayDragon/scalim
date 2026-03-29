from typing import ClassVar, Dict, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import (
    DEFAULT_BATCH_SIZE,
    DESC_LOADER_RETRY,
    DESC_LOADER_RETRY_MD,
    DESC_MAIN_SOURCE,
    DESC_MAIN_SOURCE_MD,
    DESC_OBSERVABILITY,
    DESC_OBSERVABILITY_MD,
    schema_meta,
    schema_omit,
    schema_ref,
)
from .field import DerivedFieldConfig, SourceFieldConfig
from .guardrails import GuardrailsConfig
from .lookup_bind_relation import RelationConfig
from .observability import ObservabilityConfig
from .outputs import OutputExtraSheetConfig, OutputsDefaultsConfig, OutputTargetConfig
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
        metadata=schema_meta(
            desc="批处理大小(null 或 >=1 的整数)",
            md=("批处理大小.\n\n- 未声明时使用默认值\n- `null` 表示禁用分批(单批执行)\n- `>=1` 的整数表示固定分批大小"),
            schema={
                "oneOf": [
                    {"type": "null"},
                    {"type": "integer", "minimum": 1},
                ]
            },
            default=DEFAULT_BATCH_SIZE,
            examples=[None, DEFAULT_BATCH_SIZE],
        ),
    )
    """批处理大小;`None` 表示禁用分批(单批执行)."""

    retry: Optional[LoaderRetryConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(desc=DESC_LOADER_RETRY, md=DESC_LOADER_RETRY_MD, ref="loader_retry"),
    )
    """全局加载重试配置(可选),作为默认重试策略."""

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
        metadata=schema_meta(
            desc="运行时护栏配置(可选;默认关闭)",
            md="运行时护栏配置.\n\n- 默认关闭\n- 用于控制 loader/relations/compute 等运行期护栏策略",
            ref="guardrails",
        ),
    )
    """运行时护栏配置(可选)."""

    resources: Optional[ResourcesConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            ref="resources",
            desc="可选:IO 资源声明(resources.*)",
            md="可选:IO 资源声明.\n\n- 当前稳定入口: `resources.books`",
        ),
    )
    """可选:`IO` 资源声明."""

    outputs_defaults: Optional[OutputsDefaultsConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            ref="outputs_defaults",
            desc="可选:输出默认 IO 绑定(outputs_defaults.*)",
            md="可选:输出默认 IO 绑定.\n\n- 例如 `outputs_defaults.to.book`",
        ),
    )
    """可选:输出默认 `IO` 绑定."""

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
        metadata=schema_meta(
            desc="预检查: 字段有效展示名全局唯一(默认 true)",
            md=(
                "预检查: 字段有效展示名(`effective display name`)全局唯一.\n\n"
                "- 默认启用: 未声明时等价 `true`\n"
                "- 有效展示名定义:\n"
                "  - 若 `field.name` 非空: 使用 `name`\n"
                "  - 否则回退为 `field_id`\n"
                "- 仅当 `effective outputs` 使用 `container.include_header: true`(显式或默认)\n"
                "  且 `container.header_fields_output_by: name` 时触发\n"
                "- 显式设置为 `false` 可关闭该检查(不推荐长期使用)"
            ),
            default=True,
            examples=[True, False],
        ),
    )
    """预检查:字段有效展示名(`effective display name`)全局唯一."""

    failure_policy: str = dataclass_field(
        default="all_fail",
        metadata=schema_meta(
            desc="多输出失败策略(all_fail/primary_only)",
            md=("多输出失败策略.\n\n- `all_fail`: 任一目标失败即失败\n- `primary_only`: 非主输出失败将被禁用但不阻断主输出"),
            choices=["all_fail", "primary_only"],
            default="all_fail",
            examples=["all_fail"],
        ),
    )
    """多输出失败策略."""

    include_full_error_message: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="包含完整错误信息(可能包含敏感信息;默认 false)",
            md="包含完整错误信息(可能包含敏感信息;默认 false).",
            default=False,
            examples=[False],
        ),
    )
    """是否包含完整错误信息."""

    meta: Optional[OutputExtraSheetConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {"type": "boolean"},
                    {"$ref": "#/definitions/output_extra_sheet"},
                ]
            },
            desc="可选:启用 meta sheet(写入运行信息与统计)",
            md=("可选:启用 meta sheet.\n\n- `true` 表示启用并使用默认配置\n- 对象形式可覆盖 sheet 名称与 workbook 路径"),
            examples=[True, {"sheet": "__meta__"}],
        ),
    )
    """可选:启用 `meta` 工作表."""

    audit: Optional[OutputExtraSheetConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {"type": "boolean"},
                    {"$ref": "#/definitions/output_extra_sheet"},
                ]
            },
            desc="可选:启用 audit sheet(写入目标失败等审计信息)",
            md=("可选:启用 audit sheet.\n\n- `true` 表示启用并使用默认配置\n- 对象形式可覆盖 sheet 名称与 workbook 路径"),
            examples=[True, {"sheet": "__audit__"}],
        ),
    )
    """可选:启用 `audit` 工作表."""

    observability: Optional[ObservabilityConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc=DESC_OBSERVABILITY,
            md=DESC_OBSERVABILITY_MD,
            ref="observability",
        ),
    )
    """可观测性配置(可选)."""


__all__ = []
