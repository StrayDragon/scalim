from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, ClassVar, Optional, Tuple

from ..constants import DEFAULT_GUARDRAILS_MODE, GUARDRAILS_MODE_ENUM, schema_meta


@dataclass(frozen=True)
class GuardrailsLoaderConfig:
    SCHEMA_NAME: ClassVar[str] = "guardrails_loader"
    """加载器护栏配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    validate_result: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="校验 loader 返回结构(契约校验)",
            md="校验 loader 返回结构(契约校验).\n\n- 启用时,契约违规始终 fast_fail(即使 mode=quiet)",
            default=False,
        ),
    )
    """是否校验加载器返回结构(契约校验)."""

    required_fields: Tuple[Any, ...] = dataclass_field(
        default=(),
        metadata=schema_meta(
            desc="关键字段列表(缺失/None 触发护栏;支持 field_id 字符串或 YAML alias)",
            md=(
                "关键字段列表.\n\n"
                "- 缺失/None 触发护栏\n"
                "- 为空表示不启用缺失检查\n"
                "- 每项支持 `field_id` 字符串或 YAML alias(指向已定义字段对象)\n"
                "- YAML merge(`<<`) 会生成新对象并丢失 alias 身份; merge 产物请用字符串 field_id"
            ),
            items={"anyOf": [{"type": "string"}, {"type": "object"}]},
        ),
    )
    """关键字段列表(缺失或为 `None` 时触发护栏)."""

    on_transform_error: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="字段转换异常策略(可选;默认继承 mode)",
            md="字段转换异常策略.\n\n- 作用于 extractor/value_cast/value_formatter/transform 等异常\n- 为空则继承 guardrails.mode",
            choices=GUARDRAILS_MODE_ENUM,
            examples=["fast_fail"],
        ),
    )
    """字段转换异常策略(可选;默认继承 `guardrails.mode`)."""


@dataclass(frozen=True)
class GuardrailsRelationsConfig:
    SCHEMA_NAME: ClassVar[str] = "guardrails_relations"
    """关联护栏配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    null_key_max_rate: Optional[float] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="关联 null_key 最大比例(0.0-1.0;未设置则不启用)",
            md="关联 null_key 最大比例.\n\n- 未设置则不启用阈值护栏\n- 默认对全部关联 lookup step 生效",
            min=0.0,
            max=1.0,
        ),
    )
    """关联查找中 `null_key` 的最大比例阈值(可选)."""

    type_error_max_rate: Optional[float] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="关联 type_error 最大比例(0.0-1.0;未设置则不启用)",
            md="关联 type_error 最大比例.\n\n- 未设置则不启用阈值护栏\n- 默认对全部关联 lookup step 生效",
            min=0.0,
            max=1.0,
        ),
    )
    """关联查找中 `type_error` 的最大比例阈值(可选)."""


@dataclass(frozen=True)
class GuardrailsComputeConfig:
    SCHEMA_NAME: ClassVar[str] = "guardrails_compute"
    """派生字段计算护栏配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    on_error: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="派生字段 compute 异常策略(可选;默认继承 mode)",
            md="派生字段 compute 异常策略.\n\n- 为空则继承 guardrails.mode",
            choices=GUARDRAILS_MODE_ENUM,
            examples=["fast_fail"],
        ),
    )
    """派生字段计算异常策略(可选;默认继承 `guardrails.mode`)."""


@dataclass(frozen=True)
class GuardrailsConfig:
    SCHEMA_NAME: ClassVar[str] = "guardrails"
    """护栏配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="启用运行时护栏(默认关闭)",
            md="启用运行时护栏.\n\n- 默认关闭(不改变现有行为)\n- 显式 enabled=true 才生效",
            default=False,
        ),
    )
    """是否启用运行时护栏."""

    mode: str = dataclass_field(
        default=DEFAULT_GUARDRAILS_MODE,
        metadata=schema_meta(
            desc="护栏模式(quiet/fast_fail)",
            md=("护栏模式.\n\n- `quiet`: 不抛异常,但 best-effort 记录错误事件\n- `fast_fail`: 首次触发即失败并终止 pipeline"),
            choices=GUARDRAILS_MODE_ENUM,
            default=DEFAULT_GUARDRAILS_MODE,
            examples=["fast_fail"],
        ),
    )
    """护栏模式:`quiet` 或 `fast_fail`."""

    loader: Optional[GuardrailsLoaderConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(ref="guardrails_loader"),
    )
    """加载器护栏子配置(可选)."""

    relations: Optional[GuardrailsRelationsConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(ref="guardrails_relations"),
    )
    """关联护栏子配置(可选)."""

    compute: Optional[GuardrailsComputeConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(ref="guardrails_compute"),
    )
    """派生字段计算护栏子配置(可选)."""
