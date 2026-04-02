from typing import ClassVar, Dict, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import schema_meta


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
