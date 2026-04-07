from typing import ClassVar, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import schema_meta


@dataclass(frozen=True)
class ScalimYamlLspKindOverrideConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_lsp_kind_override"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("glob", "kind")

    glob: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="按文件路径覆盖 YAML 类型(demand/workflow), glob 相对 project root",
            md="按文件路径覆盖 YAML 类型(demand/workflow), glob 相对 `project root`.",
            minLength=1,
            examples=["workflow/*.yaml"],
        ),
    )

    kind: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="YAML 类型覆盖(demand/workflow)",
            md="YAML 类型覆盖.\n\n- 允许值: `demand` / `workflow`",
            choices=["demand", "workflow"],
            examples=["workflow"],
        ),
    )


@dataclass(frozen=True)
class ScalimYamlLspConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_lsp"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    python_roots: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: 用于静态解析 Python 引用的搜索根(相对 scalim.yaml 所在目录)",
            md="用于静态解析 Python 引用的搜索根(相对 `scalim.yaml` 所在目录).",
            type=["array", "null"],
            items={"type": "string", "minLength": 1},
            default=[],
            examples=[[".", "./src"]],
        ),
    )

    kind_overrides: Tuple[ScalimYamlLspKindOverrideConfig, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: 按文件路径覆盖 YAML 类型(demand/workflow), glob 相对 project root",
            md="按文件路径覆盖 YAML 类型(demand/workflow), glob 相对 `project root`.",
            type=["array", "null"],
            default=[],
            examples=[[{"glob": "workflow/*.yaml", "kind": "workflow"}]],
        ),
    )


@dataclass(frozen=True)
class ScalimYamlImportRootConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_import_root"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("path",)

    path: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="imports roots 注册表条目: 目录路径(相对 scalim.yaml 所在目录)",
            md=(
                "imports roots 注册表条目中的目录路径(相对 `scalim.yaml` 所在目录).\n\n"
                "该路径用于两类用途:\n"
                "- 当调用侧未显式提供 `allowed_yaml_roots` 时,作为 imports 默认 allow-roots 的扩展输入\n"
                "- 当条目配置了 `alias` 时,作为 `imports.*` 的路径解析基准目录"
            ),
            minLength=1,
            examples=["./fragments"],
        ),
    )

    alias: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选: imports 路径别名(例如 @ / fragments)",
            md=(
                "可选: imports 路径别名.\n\n"
                "- 当 alias 为 `@` 时,允许在 `imports.*` 中使用 `@/x.yaml`\n"
                "- 其他 alias 允许使用 `<alias>:/x.yaml`"
            ),
            type=["string", "null"],
            minLength=1,
            default=None,
            examples=["fragments", "@"],
        ),
    )


@dataclass(frozen=True)
class ScalimYamlYamlDslConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_yaml_dsl"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    import_roots: Tuple[ScalimYamlImportRootConfig, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: imports roots 注册表(目录注册 + alias 可选)",
            md=(
                "imports roots 注册表.\n\n"
                "- 每个条目为 `{path: <dir>, alias?: <alias>}`\n"
                "- `path` 相对 `scalim.yaml` 所在目录\n"
                "- 当未显式提供 `allowed_yaml_roots` 时,这些 roots 会扩展 imports 默认 allow-roots\n"
                "- 当条目提供 `alias` 时,可在 `imports.*` 中使用 `@/x.yaml` 或 `<alias>:/x.yaml`"
            ),
            type=["array", "null"],
            items={"$ref": "#/definitions/scalim_yaml_import_root"},
            default=[],
            examples=[[{"path": "./fragments", "alias": "fragments"}, {"path": "./shared_yaml"}]],
        ),
    )

    lsp: Optional[ScalimYamlLspConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {"$ref": "#/definitions/scalim_yaml_lsp"},
                    {"type": "null"},
                ]
            },
            desc="可选: LSP project discovery 配置",
            md="LSP project discovery 配置(可选).",
            default=None,
        ),
    )


@dataclass(frozen=True)
class ScalimYamlConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = True

    yaml_dsl: Optional[ScalimYamlYamlDslConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {"$ref": "#/definitions/scalim_yaml_yaml_dsl"},
                    {"type": "null"},
                ]
            },
            desc="YAML DSL 相关配置(可选)",
            md="YAML DSL 相关配置(可选).",
            default=None,
        ),
    )


__all__ = ()
