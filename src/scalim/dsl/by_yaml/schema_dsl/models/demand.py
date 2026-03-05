# pyright: reportPrivateUsage=false

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import ClassVar, Dict, Optional

from ..constants import (
    DEFAULT_BATCH_SIZE,
    DESC_LOADER_RETRY,
    DESC_LOADER_RETRY_MD,
    DESC_MAIN_SOURCE,
    DESC_MAIN_SOURCE_MD,
    DESC_OBSERVABILITY,
    DESC_OBSERVABILITY_MD,
    _schema_meta,
    _schema_omit,
    _schema_ref,
)
from .field import DerivedFieldConfig, OutputConfig, SourceFieldConfig
from .guardrails import GuardrailsConfig
from .lookup_bind_relation import RelationConfig
from .observability import ObservabilityConfig
from .source import LoaderRetryConfig, MainSourceConfig, SourceConfig


@dataclass(frozen=True)
class DemandConfig:
    SCHEMA_NAME: ClassVar[str] = "demand"
    """配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    name: str = dataclass_field(
        default="",
        metadata=_schema_meta(
            desc="需求配置名称",
            md="需求配置名称.\n\n- 必填, 用于标识当前配置",
            examples=["order_report"],
        ),
    )
    """需求配置名称,用于标识当前需求."""

    description: str = dataclass_field(default="", metadata=_schema_meta(desc="配置描述", md="配置描述(可选)."))
    """配置说明(可选)."""

    batch_size: Optional[int] = dataclass_field(
        default=DEFAULT_BATCH_SIZE,
        metadata=_schema_meta(
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
        metadata=_schema_meta(desc=DESC_LOADER_RETRY, md=DESC_LOADER_RETRY_MD, ref="loader_retry"),
    )
    """全局加载重试配置(可选),作为默认重试策略."""

    main_source: MainSourceConfig = dataclass_field(
        default_factory=MainSourceConfig,
        metadata=_schema_meta(desc=DESC_MAIN_SOURCE, md=DESC_MAIN_SOURCE_MD, ref="main_source"),
    )
    """主数据源配置."""

    sources: Dict[str, SourceConfig] = dataclass_field(
        default_factory=dict,
        metadata=_schema_meta(
            desc="数据源配置映射, key 为 source_id",
            md=(
                "数据源配置映射, key 为 `source_id`.\n\n"
                "- 每个 source 必填: `loader`, `key`\n"
                "- 不允许包含 `main_source.source_id`\n"
                "- `fields` 仅允许源字段(禁止 `compute`)"
            ),
            additional_props=_schema_ref("source"),
            min_props=0,
        ),
    )
    """额外数据源配置映射,键为 `source_id`."""

    source_fields: Dict[str, SourceFieldConfig] = dataclass_field(default_factory=dict, metadata=_schema_omit())
    """解析后汇总的源字段配置映射(内部字段)."""

    derived_fields: Dict[str, DerivedFieldConfig] = dataclass_field(default_factory=dict, metadata=_schema_omit())
    """解析后汇总的派生字段配置映射(内部字段)."""

    source_field_id_map: Dict[str, Dict[str, str]] = dataclass_field(default_factory=dict, metadata=_schema_omit())
    """按数据源分组的字段标识映射(内部字段)."""

    relations: Dict[str, RelationConfig] = dataclass_field(
        default_factory=dict,
        metadata=_schema_meta(
            desc="命名关联关系映射(steps 模板),供 fields.*.relation 通过 alias 复用; alias 需先定义",
            md=(
                "命名关联关系映射(steps 模板).\n\n"
                "- 供 `fields.*.relation` 通过 YAML alias 复用\n"
                "- alias 需先定义 (YAML anchor)\n"
                "- steps 必须是等值关联链, 参考 `relation.steps`"
            ),
            additional_props=_schema_ref("relation"),
        ),
    )
    """命名关联关系映射,供字段通过别名复用."""

    guardrails: Optional[GuardrailsConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="运行时护栏配置(可选;默认关闭)",
            md="运行时护栏配置.\n\n- 默认关闭\n- 用于控制 loader/relations/compute 等运行期护栏策略",
            ref="guardrails",
        ),
    )
    """运行时护栏配置(可选)."""

    output: Optional[OutputConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="输出配置",
            md=(
                "输出配置.\n\n"
                "- 可选: 不写 `output` 时使用默认输出策略\n"
                "- 推荐: 把 `YAML` 当模板使用,在 Python 调用侧用 `overrides.output.*` 覆盖输出策略\n"
                "- 默认 `format: csv`\n"
                "- 字段重复时需要显式 `output.fields` 进行消歧"
            ),
            ref="output",
        ),
    )
    """输出配置(可选)."""

    observability: Optional[ObservabilityConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc=DESC_OBSERVABILITY,
            md=DESC_OBSERVABILITY_MD,
            ref="observability",
        ),
    )
    """可观测性配置(可选)."""
