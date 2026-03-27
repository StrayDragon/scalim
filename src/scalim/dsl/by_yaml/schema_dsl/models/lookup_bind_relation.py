from typing import ClassVar, Optional, Tuple, Union

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import (
    BIND_AS_ENUM,
    BIND_CACHE_MODE_ENUM,
    BIND_KEYS_SCHEMA,
    BIND_ROWS_SCHEMA,
    DEFAULT_BIND_AS,
    DEFAULT_BIND_CACHE_MODE,
    DESC_BIND_AS,
    DESC_BIND_CACHE_MODE,
    DESC_BIND_PARAM,
    DESC_LOOKUP_CAST_MD,
    DESC_RELATION_STEPS,
    LOOKUP_CAST_NAME_ENUM,
    LOOKUP_CAST_SCHEMA,
    RELATION_STEP_FROM_SCHEMA,
    RELATION_STEP_TO_SCHEMA,
    RELATION_STEPS_SCHEMA,
    schema_meta,
    schema_omit,
)


@dataclass(frozen=True)
class LookupCastConfig:
    SCHEMA_NAME: ClassVar[str] = "lookup_cast"
    """查找键归一化配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("name",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    name: str = dataclass_field(
        default="auto",
        metadata=schema_meta(
            desc="转换名称(auto/int/str/sep_first)",
            md=DESC_LOOKUP_CAST_MD,
            choices=LOOKUP_CAST_NAME_ENUM,
        ),
    )
    """转换名称(例如 `auto`/`int`/`str`/`sep_first`)."""

    sep: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(desc="sep_first 的分隔符(默认 ,)", md="sep_first 的分隔符, 默认 `,`."),
    )
    """当 `name=sep_first` 时使用的分隔符(可选)."""


@dataclass(frozen=True)
class BindRowsConfig:
    SCHEMA_NAME: ClassVar[str] = "bind_rows"
    """`rows` 模式参数绑定配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("param",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    param: str = dataclass_field(
        default="",
        metadata=schema_meta(desc=DESC_BIND_PARAM, md="下游 loader 参数名.\n\n- 仅 rows 模式生效"),
    )
    """下游加载器参数名(仅 `rows` 模式生效)."""

    cache_mode: str = dataclass_field(
        default=DEFAULT_BIND_CACHE_MODE,
        metadata=schema_meta(
            desc=DESC_BIND_CACHE_MODE,
            md="rows 缓存策略.\n\n- `batch`: 批次内复用\n- `none`: 不复用",
            choices=BIND_CACHE_MODE_ENUM,
            default=DEFAULT_BIND_CACHE_MODE,
            examples=["batch"],
        ),
    )
    """`rows` 模式缓存策略:`batch` 或 `none`."""


@dataclass(frozen=True)
class BindKeysConfig:
    SCHEMA_NAME: ClassVar[str] = "bind_keys"
    """`keys` 模式参数绑定配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("param",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    param: str = dataclass_field(
        default="",
        metadata=schema_meta(desc=DESC_BIND_PARAM, md="下游 loader 参数名.\n\n- 仅 keys 模式生效"),
    )
    """下游加载器参数名(仅 `keys` 模式生效)."""

    as_: str = dataclass_field(
        default=DEFAULT_BIND_AS,
        metadata=schema_meta(
            desc=DESC_BIND_AS,
            md="keys 容器类型.\n\n- `set`: 去重\n- `list`: 保持顺序",
            choices=BIND_AS_ENUM,
            default=DEFAULT_BIND_AS,
            schema_name="as",
            examples=["set"],
        ),
    )
    """`keys` 模式容器类型:`set` 或 `list`."""


@dataclass(frozen=True)
class BindConfig:
    SCHEMA_NAME: ClassVar[str] = "bind"
    """参数绑定配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ()
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    use_rows: Optional[BindRowsConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(schema=BIND_ROWS_SCHEMA, schema_name="use_rows"),
    )
    """可选:使用 `rows` 模式的绑定配置."""

    use_keys: Optional[BindKeysConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(schema=BIND_KEYS_SCHEMA, schema_name="use_keys"),
    )
    """可选:使用 `keys` 模式的绑定配置."""


@dataclass(frozen=True)
class RelationStepConfig:
    SCHEMA_NAME: ClassVar[str] = "relation_step"
    """关联步骤配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("from", "to")
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    from_: Union[str, Tuple[str, ...]] = dataclass_field(
        default="",
        metadata=schema_meta(schema=RELATION_STEP_FROM_SCHEMA, schema_name="from"),
    )
    """关联起点字段名(对应 `from`)."""

    to: Union[str, Tuple[str, ...]] = dataclass_field(
        default="",
        metadata=schema_meta(schema=RELATION_STEP_TO_SCHEMA),
    )
    """关联终点字段名."""

    lookup_cast: Optional[LookupCastConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=LOOKUP_CAST_SCHEMA,
            desc="对 from 值进行归一化的转换(仅影响本 step)",
            md="对 `from` 值进行归一化(仅影响当前 step).",
        ),
    )
    """可选:对 `from` 值进行归一化的转换(仅影响当前步骤)."""


@dataclass(frozen=True)
class RelationConfig:
    SCHEMA_NAME: ClassVar[str] = "relation"
    """命名关联关系配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("steps",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    relation_id: str = dataclass_field(default="", metadata=schema_omit())
    """关联关系标识(内部字段;由外层映射键提供)."""

    steps: Tuple[RelationStepConfig, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(schema=RELATION_STEPS_SCHEMA, desc=DESC_RELATION_STEPS),
    )
    """关系路径的步骤列表."""


@dataclass(frozen=True)
class InlineRelationConfig:
    SCHEMA_NAME: ClassVar[str] = "relation_inline"
    """内联关联关系配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("steps",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    steps: Tuple[RelationStepConfig, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(schema=RELATION_STEPS_SCHEMA, desc=DESC_RELATION_STEPS),
    )
    """关系路径的步骤列表."""


__all__ = []
