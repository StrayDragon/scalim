from typing import ClassVar, Dict, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import schema_meta


@dataclass(frozen=True)
class ScalimYamlYamlDslRunnerConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_yaml_dsl_runner"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    allowed_modules: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: CLI runner 默认 allowlist modules",
            md=(
                "CLI runner 默认 allowlist modules.\n\n"
                "- 仅用于提供默认值(减少重复 flags)\n"
                "- allowlist 为空仍会 fail-fast(不弱化安全边界)\n"
                "- 可被 CLI flags 覆盖"
            ),
            type=["array", "null"],
            items={"type": "string", "minLength": 1},
            default=[],
            examples=[["myapp.loaders"]],
        ),
    )

    allowed_functions: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: CLI runner 默认 allowlist functions",
            md=("CLI runner 默认 allowlist functions.\n\n- 仅用于提供默认值(减少重复 flags)\n- 可被 CLI flags 覆盖"),
            type=["array", "null"],
            items={"type": "string", "minLength": 1},
            default=[],
            examples=[["myapp.loaders:load_orders"]],
        ),
    )

    allowed_yaml_roots: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: 允许读取 YAML 的根目录列表(相对 scalim.yaml 所在目录)",
            md="允许读取 YAML 的根目录列表(相对 `scalim.yaml` 所在目录).",
            type=["array", "null"],
            items={"type": "string", "minLength": 1},
            default=[],
            examples=[["./shared_yaml"]],
        ),
    )

    template_sandbox: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:模板 sandbox 默认值",
            md="模板 sandbox 默认值.\n\n- 允许值: `safe` / `legacy`",
            type=["string", "null"],
            choices=["safe", "legacy"],
            default=None,
            examples=["safe"],
        ),
    )

    parallel_mode: Optional[str] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:并行模式默认值",
            md="并行模式默认值.\n\n- 允许值: `seq` / `adaptive`",
            type=["string", "null"],
            choices=["seq", "adaptive"],
            default=None,
            examples=["seq"],
        ),
    )

    max_workers: Optional[int] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="可选:最大并发工作数默认值(0 自动)",
            md="最大并发工作数默认值.\n\n- `0` 表示自动",
            type=["integer", "null"],
            minimum=0,
            default=None,
            examples=[0, 8],
        ),
    )


@dataclass(frozen=True)
class ScalimYamlEditorKindOverrideConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_editor_kind_override"
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
class ScalimYamlEditorConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_editor"
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

    kind_overrides: Tuple[ScalimYamlEditorKindOverrideConfig, ...] = dataclass_field(
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
class ScalimYamlYamlDslConfig:
    SCHEMA_NAME: ClassVar[str] = "scalim_yaml_yaml_dsl"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    import_aliases: Dict[str, str] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="可选: imports 目录别名映射(用于 fragments 路径解析与 allow roots 扩展)",
            md=(
                "imports 目录别名映射.\n\n"
                "- key: alias\n"
                "- value: directory path(相对 `scalim.yaml` 所在目录)\n"
                "- 会同时用于扩展 allow roots(允许读取 YAML fragments 的范围)"
            ),
            type=["object", "null"],
            propertyNames={"type": "string", "minLength": 1},
            additional_props={"type": "string", "minLength": 1},
            default={},
            examples=[{"shared": "./shared_yaml"}],
        ),
    )

    import_allowed_roots: Tuple[str, ...] = dataclass_field(
        default_factory=tuple,
        metadata=schema_meta(
            desc="可选: 允许读取 YAML fragments 的根目录列表(相对 scalim.yaml 所在目录)",
            md="允许读取 YAML fragments 的根目录列表(相对 `scalim.yaml` 所在目录).",
            type=["array", "null"],
            items={"type": "string", "minLength": 1},
            default=[],
            examples=[["./shared_yaml"]],
        ),
    )

    editor: Optional[ScalimYamlEditorConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {"$ref": "#/definitions/scalim_yaml_editor"},
                    {"type": "null"},
                ]
            },
            desc="可选: editor/LSP project discovery 配置",
            md="editor/LSP project discovery 配置(可选).",
            default=None,
        ),
    )

    runner: Optional[ScalimYamlYamlDslRunnerConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema={
                "oneOf": [
                    {"$ref": "#/definitions/scalim_yaml_yaml_dsl_runner"},
                    {"type": "null"},
                ]
            },
            desc="可选: CLI runner 默认值(yaml_dsl.runner.*)",
            md="CLI runner 默认值(可选).\n\n- 用于 `scalim-cli yaml-dsl run` / `workflow run`",
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
