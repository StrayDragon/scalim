from typing import Any, ClassVar, Dict, Optional, Tuple, Union

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import (
    DEFAULT_CACHE_MODE,
    DEFAULT_LOADER_RETRY_BACKOFF,
    DEFAULT_LOADER_RETRY_BASE_DELAY_SECONDS,
    DEFAULT_LOADER_RETRY_ENABLED,
    DEFAULT_LOADER_RETRY_JITTER,
    DEFAULT_LOADER_RETRY_MAX_ATTEMPTS,
    DEFAULT_LOADER_RETRY_MAX_DELAY_SECONDS,
    DEFAULT_LOADER_RETRY_MAX_ELAPSED_SECONDS,
    DEFAULT_NORMALIZE_ON_CONFLICT,
    DESC_LOADER,
    DESC_LOADER_MD,
    DESC_LOADER_RETRY,
    DESC_LOADER_RETRY_MD,
    DESC_LOOKUP_CAST,
    DESC_LOOKUP_CAST_MD,
    DESC_MAIN_SOURCE_ORDER_BY,
    DESC_MAIN_SOURCE_ORDER_BY_MD,
    DESC_PARAMS,
    DESC_PARAMS_MD,
    DESC_SOURCE_NORMALIZE,
    DESC_SOURCE_NORMALIZE_MD,
    FIELD_ID_STRING_SCHEMA,
    HARD_CAP_LOADER_RETRY_MAX_ATTEMPTS,
    HARD_CAP_LOADER_RETRY_MAX_DELAY_SECONDS,
    HARD_CAP_LOADER_RETRY_MAX_ELAPSED_SECONDS,
    LOADER_RETRY_BACKOFF_ENUM,
    LOOKUP_CAST_SCHEMA,
    LOOKUP_CHUNK_SIZE_SCHEMA,
    NORMALIZE_SCHEMA,
    SOURCE_ID_STRING_SCHEMA,
    schema_meta,
    schema_omit,
    schema_ref,
)
from .field import SourceFieldConfig
from .lookup_bind_relation import LookupCastConfig


@dataclass(frozen=True)
class LoaderRetryConfig:
    SCHEMA_NAME: ClassVar[str] = "loader_retry"
    """加载重试配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: Optional[bool] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc=DESC_LOADER_RETRY,
            md=(
                DESC_LOADER_RETRY_MD
                + "\n\n"
                + "注意:\n"
                + "- 当 enabled=true 时需要提供 `should_retry`\n"
                + "- 若未提供 `should_retry`, 仅当 driver 注入提供回调时才允许启用"
            ),
            default=DEFAULT_LOADER_RETRY_ENABLED,
        ),
    )
    """是否启用加载重试(可选;为空则使用默认值)."""

    should_retry: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="重试判定回调引用(安全引用,由 allowlist 约束)",
            md=(
                "重试判定回调引用.\n\n"
                "- 形式与 `loader` 引用一致:\n"
                "  - 绝对引用: `module.path.function` / `module.path:function` / `module.path:obj.method`\n"
                "  - 相对引用: 以 `.` / `..` 开头的 module path(相对 YAML 文件所在目录)\n"
                "- 相对引用会在运行期先归一化为绝对引用,并继续受 allowlist(allowed_modules/allowed_functions) 约束\n"
                "- 签名: `should_retry(exc, ctx) -> bool`"
            ),
            minLength=1,
            examples=["myapp.retry:should_retry_db", ".retry:should_retry_db"],
        ),
    )
    """重试判定回调引用(受允许列表约束)."""

    max_attempts: Optional[int] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="最大尝试次数(含首次)",
            md="最大尝试次数(含首次调用).\n\n- 受硬上限保护: <= 5",
            min=1,
            max=HARD_CAP_LOADER_RETRY_MAX_ATTEMPTS,
            default=DEFAULT_LOADER_RETRY_MAX_ATTEMPTS,
            examples=[DEFAULT_LOADER_RETRY_MAX_ATTEMPTS],
        ),
    )
    """最大尝试次数(包含首次调用,可选)."""

    max_elapsed_seconds: Optional[float] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="最大累计耗时(秒,包含 sleep)",
            md="最大累计耗时(秒,包含 sleep).\n\n- 受硬上限保护: <= 20",
            min=0.000_001,
            max=HARD_CAP_LOADER_RETRY_MAX_ELAPSED_SECONDS,
            default=DEFAULT_LOADER_RETRY_MAX_ELAPSED_SECONDS,
            examples=[DEFAULT_LOADER_RETRY_MAX_ELAPSED_SECONDS],
        ),
    )
    """最大累计耗时(秒,包含等待,可选)."""

    backoff: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="退避策略(fixed/exponential)",
            md=("退避策略.\n\n- `fixed`: 固定等待\n- `exponential`: 指数退避"),
            choices=LOADER_RETRY_BACKOFF_ENUM,
            default=DEFAULT_LOADER_RETRY_BACKOFF,
            examples=[DEFAULT_LOADER_RETRY_BACKOFF],
        ),
    )
    """退避策略:`fixed` 或 `exponential`(可选)."""

    base_delay_seconds: Optional[float] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="基础等待时间(秒)",
            md="基础等待时间(秒).\n\n- fixed: 每次等待 base_delay\n- exponential: base_delay * 2**(attempt-1)",
            min=0.0,
            default=DEFAULT_LOADER_RETRY_BASE_DELAY_SECONDS,
            examples=[DEFAULT_LOADER_RETRY_BASE_DELAY_SECONDS],
        ),
    )
    """基础等待时间(秒,可选)."""

    max_delay_seconds: Optional[float] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="最大单次等待时间(秒)",
            md="最大单次等待时间(秒).\n\n- 受硬上限保护: <= 5",
            min=0.0,
            max=HARD_CAP_LOADER_RETRY_MAX_DELAY_SECONDS,
            default=DEFAULT_LOADER_RETRY_MAX_DELAY_SECONDS,
            examples=[DEFAULT_LOADER_RETRY_MAX_DELAY_SECONDS],
        ),
    )
    """最大单次等待时间(秒,可选)."""

    jitter: Optional[bool] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="启用 jitter(随机扰动)",
            md="启用 jitter(随机扰动),避免重试风暴.\n\n- true: 在 [0, delay] 区间内随机\n- false: 精确使用 delay",
            default=DEFAULT_LOADER_RETRY_JITTER,
            examples=[DEFAULT_LOADER_RETRY_JITTER],
        ),
    )
    """是否启用随机扰动,避免重试风暴(可选)."""


@dataclass(frozen=True)
class NormalizeProjectFieldRuleConfig:
    SCHEMA_NAME: ClassVar[str] = "normalize_project_field_rule"
    """用于 `normalize.fields.<name>` 的规则对象(内部模型)."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ()
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    from_key: Optional[bool] = dataclass_field(default=None)
    """将 `lookup key` 注入该字段(可选)."""

    extract: Optional[str] = dataclass_field(default=None)
    """从 `row value` 中提取字段值的路径表达式(可选)."""


@dataclass(frozen=True)
class NormalizeStepConfig:
    SCHEMA_NAME: ClassVar[str] = "normalize_step"
    """用于 `normalize.steps` 的步骤配置对象(内部模型)."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("kind",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    kind: str = dataclass_field(default="")
    """`normalize` 步骤类型."""

    on_empty: Optional[str] = dataclass_field(default=None)
    """空列表策略(仅 `take_first`)."""

    on_missing: Optional[str] = dataclass_field(default=None)
    """缺失路径策略(仅 `project_fields`)."""

    fields: Dict[str, NormalizeProjectFieldRuleConfig] = dataclass_field(default_factory=dict)
    """`project_fields` 的投影规则."""


@dataclass(frozen=True)
class NormalizeConfig:
    SCHEMA_NAME: ClassVar[str] = "normalize"
    """`whole-result` `normalize` 配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("kind",)
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    kind: str = dataclass_field(default="")
    """`normalize` 预置类型."""

    key_field: str = dataclass_field(default="")
    """用于建立索引的 `row` 字段名."""

    on_conflict: str = dataclass_field(default=DEFAULT_NORMALIZE_ON_CONFLICT)
    """`duplicate key` 冲突策略."""

    on_empty: Optional[str] = dataclass_field(default=None)
    """空列表策略(仅 `take_first`)."""

    on_missing: Optional[str] = dataclass_field(default=None)
    """缺失路径策略(仅 `project_fields`)."""

    fields: Dict[str, NormalizeProjectFieldRuleConfig] = dataclass_field(default_factory=dict)
    """`project_fields` 的投影规则."""

    steps: Tuple[NormalizeStepConfig, ...] = dataclass_field(default_factory=tuple)
    """用于 `normalize.kind: map_values` 的步骤列表."""

    call_by: Optional[str] = dataclass_field(default=None)
    """可选: `normalize` 受控扩展点(安全引用)."""


@dataclass(frozen=True)
class SourceConfig:
    SCHEMA_NAME: ClassVar[str] = "source"
    """数据源配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("loader", "key")
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    source_id: str = dataclass_field(default="", metadata=schema_omit())
    """数据源标识(内部字段;由外层映射键提供)."""

    loader: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc=DESC_LOADER,
            md=DESC_LOADER_MD,
            minLength=1,
            examples=["myapp.loaders:load_orders", "^workflow/book_sheet_rows"],
        ),
    )
    """加载器引用(模块路径 + 可调用对象)."""

    key: Union[str, Tuple[str, ...]] = dataclass_field(
        default="",
        metadata=schema_meta(
            one_of=[
                FIELD_ID_STRING_SCHEMA,
                {"type": "array", "items": FIELD_ID_STRING_SCHEMA, "minItems": 1},
            ],
            desc="该 source loader 返回映射的 key 字段(支持复合键 tuple)",
            md=("该 source loader 返回映射的 key 字段.\n\n- 单字段: `key: order_id`\n- 复合键: `key: [region_id, institution_id]`"),
            examples=["order_id", ["region_id", "institution_id"]],
        ),
    )
    """加载器返回映射的主键字段(支持复合键)."""

    lookup_cast: Optional[LookupCastConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(schema=LOOKUP_CAST_SCHEMA, desc=DESC_LOOKUP_CAST, md=DESC_LOOKUP_CAST_MD),
    )
    """可选:查找键归一化配置."""

    lookup_chunk_size: Optional[int] = dataclass_field(
        default=None,
        metadata=schema_meta(schema=LOOKUP_CHUNK_SIZE_SCHEMA),
    )
    """可选:查找键分块大小."""

    normalize: Optional[NormalizeConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(schema=NORMALIZE_SCHEMA, desc=DESC_SOURCE_NORMALIZE, md=DESC_SOURCE_NORMALIZE_MD),
    )
    """可选: `whole-result` `normalize` 配置."""

    cache_mode: str = dataclass_field(
        default=DEFAULT_CACHE_MODE,
        metadata=schema_meta(
            desc="缓存模式:none=不缓存,preload_forever=预加载永久缓存",
            md=(
                "缓存模式.\n\n"
                "- `none`: 不缓存\n"
                "- `preload_forever`: 预加载并长期缓存\n"
                "- 设为 `preload_forever` 时,预加载阶段会执行一次 loader 并将结果缓存\n"
                "- 预加载阶段同样会复用编译后的 `sources.<id>.params` kwargs 模板(禁用 `$keys/$rows`)\n"
                "- `preload_forever` 场景禁止在 `params` 中使用 `$keys/$rows`"
            ),
            choices=["none", "preload_forever"],
            default=DEFAULT_CACHE_MODE,
        ),
    )
    """缓存模式:`none` 或 `preload_forever`."""

    retry: Optional[LoaderRetryConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(desc=DESC_LOADER_RETRY, md=DESC_LOADER_RETRY_MD, ref="loader_retry"),
    )
    """该数据源的重试配置(可选;用于覆盖默认重试策略)."""

    fields: Dict[str, SourceFieldConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="数据源字段配置映射, key 为 field_id",
            md=(
                "数据源字段配置映射.\n\n"
                "- 仅允许源字段(禁止 `compute`)\n"
                "- `source` 可省略或必须等于当前 `source_id`\n"
                "- 支持 YAML anchor 复用"
            ),
            additional_props=schema_ref("source_field_inline"),
            min_props=0,
        ),
    )
    """数据源字段配置映射,键为 `field_id`."""

    params: Dict[str, Any] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(desc=DESC_PARAMS, md=DESC_PARAMS_MD, additional_props={}),
    )
    """传递给加载器的 `kwargs` 模板(编译期解析 `{$init_var: <name>}`,运行期渲染 `$keys/$rows`)."""


@dataclass(frozen=True)
class MainSourceConfig:
    SCHEMA_NAME: ClassVar[str] = "main_source"
    """主数据源配置对象在 `YAML` 中的节点名称."""

    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("source_id", "loader")
    """该配置对象在 `YAML` 中的必填字段列表."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    source_id: str = dataclass_field(
        default="",
        metadata=schema_meta(
            schema=SOURCE_ID_STRING_SCHEMA,
            desc="主数据源的 source_id",
            md="主数据源的 `source_id`.\n\n- 必填\n- 不能与 `sources` 的 key 重复",
        ),
    )
    """主数据源的 `source_id`."""

    loader: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc=DESC_LOADER,
            md=DESC_LOADER_MD,
            minLength=1,
            examples=["myapp.loaders:load_orders", "^workflow/book_sheet_rows"],
        ),
    )
    """主数据源加载器引用."""

    fields: Dict[str, SourceFieldConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="主数据源字段配置映射, key 为 field_id",
            md=(
                "主数据源字段配置映射.\n\n"
                "- 仅允许源字段(禁止 `compute`)\n"
                "- `source` 可省略或必须等于 `main_source.source_id`\n"
                "- 支持 YAML anchor 复用"
            ),
            additional_props=schema_ref("source_field_inline"),
            min_props=0,
        ),
    )
    """主数据源字段配置映射,键为 `field_id`."""

    params: Dict[str, Any] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(desc=DESC_PARAMS, md=DESC_PARAMS_MD, additional_props={}),
    )
    """传递给主数据源加载器的静态参数映射."""

    retry: Optional[LoaderRetryConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(desc=DESC_LOADER_RETRY, md=DESC_LOADER_RETRY_MD, ref="loader_retry"),
    )
    """主数据源的重试配置(可选)."""

    order_by: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            schema={"type": "array", "items": {"type": "string"}},
            desc=DESC_MAIN_SOURCE_ORDER_BY,
            md=DESC_MAIN_SOURCE_ORDER_BY_MD,
        ),
    )
    """主数据源排序字段列表(用于稳定输出顺序,可选)."""


__all__ = ()
