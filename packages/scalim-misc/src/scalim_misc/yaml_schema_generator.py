# pragma: allow-cast-file gen-only schema generator; casts for Any-narrowing (not runtime hot path)
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple, Type, Union, cast

from scalim.dsl.yaml_dsl.schema_dsl import constants as schema_constants
from scalim.dsl.yaml_dsl.schema_dsl import models as schema_models
from scalim.dsl.yaml_dsl.schema_dsl import workflow_ssot
from scalim.dsl.yaml_dsl.schema_dsl.constants import SCHEMA_META_KEY
from scalim.vendor.dataclassesx import Field, dataclass
from scalim.vendor.dataclassesx import fields as dataclass_fields

from .yaml_schema_doc_standardizer import standardize_schema_docs

_IMPORT_KEY = "$import"
_IMPORTS_KEY = "imports"

_SCHEMA_DOC_FIXTURE_RELATIVE_PATHS: Tuple[str, ...] = (
    "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_rank_score_report.yaml",
    "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/workflow_fixture_cache_pool_pin.yaml",
    "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/scalim.yaml",
)

_YAML_MERGE_KEY = "<<"


def _property_names_schema_allows_yaml_merge_key(schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False

    if schema.get("const") == _YAML_MERGE_KEY:
        return True

    enum = schema.get("enum")
    if isinstance(enum, list) and _YAML_MERGE_KEY in enum:
        return True

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        return any(_property_names_schema_allows_yaml_merge_key(item) for item in any_of)

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        return any(_property_names_schema_allows_yaml_merge_key(item) for item in one_of)

    return False


def _allow_yaml_merge_key_in_property_names(schema: Any) -> Any:
    """对所有 `propertyNames` 统一允许 YAML merge key (`<<`).

    说明:
    - 该 post-process 目标是对齐 `yaml-language-server` 的 schema-only 校验行为
    - 仅在存在 `propertyNames` 的位置注入 `<<`,不放宽其它 key 约束
    - 幂等: 重复执行不应改变结果
    """

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            prop_names = node.get("propertyNames")
            if isinstance(prop_names, dict) and not _property_names_schema_allows_yaml_merge_key(prop_names):
                node["propertyNames"] = {"anyOf": [{"const": _YAML_MERGE_KEY}, prop_names]}

            for value in node.values():
                _walk(value)
            return

        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
    return schema


def _find_repo_root(start: Path) -> Optional[Path]:
    current = start.parent if start.is_file() else start
    for _ in range(12):
        if (current / "src" / "scalim").exists() and (current / "packages").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _resolve_schema_doc_fixture_paths() -> List[str]:
    """用于编辑器悬停提示的 `JSON Schema` 示例样例(仅生成期使用).

    说明:
    - 在仓库内生成时,这些文件可作为示例片段来源.
    - 若在安装包环境(缺少 `notebooks/` 目录)调用生成脚本,则自动降级为不启用片段示例.
    """

    repo_root = _find_repo_root(Path(__file__).resolve())
    if repo_root is None:
        return []
    resolved: List[str] = []
    for rel in _SCHEMA_DOC_FIXTURE_RELATIVE_PATHS:
        path = repo_root / rel
        if not path.exists():
            continue
        resolved.append(str(path))
    return resolved


def _build_default_types_module() -> Any:
    merged: Dict[str, Any] = {}
    # 仅复制公开名称.这样可以保持默认模块显式化,并避免动态属性回退.
    for name, value in vars(schema_constants).items():
        if name.startswith("_"):
            continue
        merged[name] = value
    for name, value in vars(schema_models).items():
        if name.startswith("_"):
            continue
        merged[name] = value
    return SimpleNamespace(**merged)


_DEFAULT_TYPES_MODULE = _build_default_types_module()


@dataclass(frozen=True)
class SchemaMeta:
    schema_name: Optional[str]
    meta: Dict[str, Any]

    @classmethod
    def from_field(cls, dc_field: "Field[Any]") -> "SchemaMeta":
        raw_meta = dict(dc_field.metadata.get(SCHEMA_META_KEY, {}))
        schema_name = raw_meta.pop("schema_name", None)
        if not isinstance(schema_name, str):
            schema_name = None
        return cls(schema_name=schema_name, meta=raw_meta)


class SchemaBuilder:
    META_KEY_MAP: ClassVar[Dict[str, str]] = {
        "desc": "description",
        "md": "markdownDescription",
        "markdown": "markdownDescription",
        "choices": "enum",
        "min": "minimum",
        "max": "maximum",
        "min_items": "minItems",
        "max_items": "maxItems",
        "min_props": "minProperties",
        "max_props": "maxProperties",
        "pattern": "pattern",
        "default": "default",
        "type": "type",
        "items": "items",
        "one_of": "oneOf",
        "any_of": "anyOf",
        "all_of": "allOf",
        "additional_props": "additionalProperties",
        "const": "const",
        "deprecated": "deprecated",
        "items_choices": "items_choices",
        "example": "examples",
    }
    ORDER_INSENSITIVE_KEYS: ClassVar[Set[str]] = {"required", "enum", "oneOf", "anyOf", "allOf"}
    IGNORED_KEYS: ClassVar[Set[str]] = {"$comment"}
    ELLIPSIS_TUPLE_LEN: ClassVar[int] = 2
    GENERATED_SCHEMA_COMMENT: ClassVar[str] = "自动生成, 请勿手动修改. 生成脚本: scripts/gen-yaml-dsl-schema.py"
    PRIMITIVE_TYPE_MAP: ClassVar[Dict[Type[Any], str]] = {
        bool: "boolean",
        int: "integer",
        float: "number",
        str: "string",
    }
    NUMERIC_CONSTRAINT_KEYS: ClassVar[Set[str]] = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
    NUMERIC_SCHEMA_TYPES: ClassVar[Set[str]] = {"number", "integer"}
    _types: Any

    def __init__(self, types_module: Optional[Any] = None) -> None:
        if types_module is None:
            types_module = _DEFAULT_TYPES_MODULE
        self._types = types_module

    def build_demand_schema(self) -> Dict[str, Any]:
        types_mod = self._types
        definitions = {
            "main_source": self._build_definition(types_mod.MainSourceConfig),
            "source": self._build_definition(types_mod.SourceConfig),
            "source_field_inline": self._build_definition(types_mod.SourceFieldConfig),
            "field": self._build_field_definition(),
            "relation": self._build_definition(types_mod.RelationConfig),
            "book_export_xlsx": self._build_definition(types_mod.BookExportXlsxConfig),
            "book_xlsx_file": self._build_definition(types_mod.BookXlsxFileConfig),
            "book_xlsx_memory": self._build_definition(types_mod.BookXlsxMemoryConfig),
            "book": self._build_definition(types_mod.BookConfig),
            "file_csv_file": self._build_definition(types_mod.FileCsvFileConfig),
            "file": self._build_definition(types_mod.FileConfig),
            "resources": self._build_definition(types_mod.ResourcesConfig),
            # `c15-yaml-dsl-demand-imports-scope`: 输出相关配置不支持 `$import` (仅允许在稳定编写入口使用)。
            "output_aggregate": self._build_definition(types_mod.OutputAggregateConfig, allow_import=False),
            "output_to": self._build_definition(types_mod.OutputToConfig, allow_import=False),
            "output_write": self._build_definition(types_mod.OutputWriteConfig, allow_import=False),
            "output_target": self._build_definition(types_mod.OutputTargetConfig, allow_import=False),
            "output_extra_sheet": self._build_definition(types_mod.OutputExtraSheetConfig, allow_import=False),
            "guardrails_loader": self._build_definition(types_mod.GuardrailsLoaderConfig),
            "guardrails_relations": self._build_definition(types_mod.GuardrailsRelationsConfig),
            "guardrails_compute": self._build_definition(types_mod.GuardrailsComputeConfig),
            "guardrails": self._build_definition(types_mod.GuardrailsConfig),
            "loader_retry": self._build_definition(types_mod.LoaderRetryConfig),
        }

        schema: Dict[str, Any] = {
            "$schema": types_mod.DEMAND_SCHEMA_META["$schema"],
            "$id": types_mod.DEMAND_SCHEMA_META["$id"],
            "title": types_mod.DEMAND_SCHEMA_META["title"],
            "description": types_mod.DEMAND_SCHEMA_META["description"],
            "$comment": self.GENERATED_SCHEMA_COMMENT,
            "type": "object",
            "required": list(types_mod.DEMAND_SCHEMA_REQUIRED),
            "properties": self._build_demand_properties(),
            "definitions": definitions,
        }
        if "markdownDescription" in types_mod.DEMAND_SCHEMA_META:
            schema["markdownDescription"] = types_mod.DEMAND_SCHEMA_META["markdownDescription"]
        additional_props = getattr(
            types_mod.DemandConfig, "SCHEMA_ADDITIONAL_PROPERTIES", None
        )  # pragma: allow-dynattr metadata: schema meta
        if additional_props is not None:
            schema["additionalProperties"] = bool(additional_props)
        schema = standardize_schema_docs(schema, fixture_paths=_resolve_schema_doc_fixture_paths())
        _ = _allow_yaml_merge_key_in_property_names(schema)
        return schema

    def build_workflow_schema(self) -> Dict[str, Any]:
        types_mod = self._types

        definitions: Dict[str, Any] = {
            "book_export_xlsx": self._build_definition(types_mod.BookExportXlsxConfig, allow_import=False),
            "book_xlsx_file": self._build_definition(types_mod.BookXlsxFileConfig, allow_import=False),
            "book_xlsx_memory": self._build_definition(types_mod.BookXlsxMemoryConfig, allow_import=False),
            "book": self._build_definition(types_mod.BookConfig, allow_import=False),
            "file_csv_file": self._build_definition(types_mod.FileCsvFileConfig, allow_import=False),
            "file": self._build_definition(types_mod.FileConfig, allow_import=False),
            "resources": self._build_definition(types_mod.ResourcesConfig, allow_import=False),
        }

        workflow = workflow_ssot.build_workflow_workflow_schema()

        schema: Dict[str, Any] = {
            "$schema": types_mod.WORKFLOW_SCHEMA_META["$schema"],
            "$id": types_mod.WORKFLOW_SCHEMA_META["$id"],
            "title": types_mod.WORKFLOW_SCHEMA_META["title"],
            "description": types_mod.WORKFLOW_SCHEMA_META["description"],
            "$comment": self.GENERATED_SCHEMA_COMMENT,
            "type": "object",
            "required": ["workflow"],
            "properties": {"workflow": workflow},
            "definitions": definitions,
            "additionalProperties": False,
        }
        self._assert_schema_does_not_expose_import_key(schema, path="$")
        schema = standardize_schema_docs(schema, fixture_paths=_resolve_schema_doc_fixture_paths())
        _ = _allow_yaml_merge_key_in_property_names(schema)
        return schema

    def build_scalim_yaml_schema(self) -> Dict[str, Any]:
        types_mod = self._types

        definitions: Dict[str, Any] = {
            "scalim_yaml_import_root": self._build_definition(
                types_mod.ScalimYamlImportRootConfig,
                allow_import=False,
            ),
            "scalim_yaml_lsp_kind_override": self._build_definition(
                types_mod.ScalimYamlLspKindOverrideConfig,
                allow_import=False,
            ),
            "scalim_yaml_lsp": self._build_definition(
                types_mod.ScalimYamlLspConfig,
                allow_import=False,
            ),
            "scalim_yaml_yaml_dsl": self._build_definition(
                types_mod.ScalimYamlYamlDslConfig,
                allow_import=False,
            ),
            "scalim_yaml": self._build_definition(
                types_mod.ScalimYamlConfig,
                allow_import=False,
            ),
        }

        schema: Dict[str, Any] = {
            "$schema": types_mod.SCALIM_YAML_SCHEMA_META["$schema"],
            "$id": types_mod.SCALIM_YAML_SCHEMA_META["$id"],
            "title": types_mod.SCALIM_YAML_SCHEMA_META["title"],
            "description": types_mod.SCALIM_YAML_SCHEMA_META["description"],
            "$comment": self.GENERATED_SCHEMA_COMMENT,
            "oneOf": [
                {"type": "null"},
                {"$ref": "#/definitions/scalim_yaml"},
            ],
            "definitions": definitions,
        }
        if "markdownDescription" in types_mod.SCALIM_YAML_SCHEMA_META:
            schema["markdownDescription"] = types_mod.SCALIM_YAML_SCHEMA_META["markdownDescription"]
        schema = standardize_schema_docs(schema, fixture_paths=_resolve_schema_doc_fixture_paths())
        _ = _allow_yaml_merge_key_in_property_names(schema)
        return schema

    def _build_definition(self, cls: type, *, allow_import: bool = True) -> Dict[str, Any]:
        types_mod = self._types
        properties = self._build_class_properties(cls, allow_import=allow_import)
        if allow_import:
            properties.setdefault(_IMPORT_KEY, copy.deepcopy(types_mod.IMPORT_REF_SCHEMA))
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }

        required = getattr(cls, "SCHEMA_REQUIRED", ())  # pragma: allow-dynattr metadata: schema meta
        if required:
            if allow_import:
                # `$import` 会在编译期展开;为提升 `LSP`/`schema` 体验,允许仅声明 `$import` 的用法通过校验.
                schema["anyOf"] = [{"required": list(required)}, {"required": [_IMPORT_KEY]}]
            else:
                schema["required"] = list(required)

        additional_props = getattr(cls, "SCHEMA_ADDITIONAL_PROPERTIES", None)  # pragma: allow-dynattr metadata: schema meta
        if additional_props is not None:
            schema["additionalProperties"] = bool(additional_props)

        all_of = getattr(cls, "SCHEMA_ALL_OF", None)  # pragma: allow-dynattr metadata: schema meta
        if all_of is not None:
            schema["allOf"] = copy.deepcopy(all_of)

        return schema

    def _build_demand_properties(self) -> Dict[str, Any]:
        types_mod = self._types
        base_properties = self._build_class_properties(types_mod.DemandConfig, allow_import=True)
        base_properties.setdefault(_IMPORTS_KEY, copy.deepcopy(types_mod.IMPORTS_SCHEMA))
        ordered: Dict[str, Any] = {}
        for name in types_mod.DEMAND_SCHEMA_PROPERTIES_ORDER:
            if name == "_templates":
                ordered[name] = {
                    "type": "object",
                    "description": "YAML anchor 模板集合(_templates), 供 fields/relations 复用",
                    "markdownDescription": "YAML anchor 模板集合.\n\n- 仅用于 YAML 复用(anchors)\n- 常用于 `fields` / `relations`",
                    "additionalProperties": True,
                }
                continue
            if name == "fields":
                ordered[name] = {
                    "type": "object",
                    "description": "字段配置映射, key 为 field_id; 仅用于派生字段",
                    "markdownDescription": (
                        "字段配置映射(仅用于派生字段).\n\n"
                        "- 必须包含 `compute` 或 `call_by`\n"
                        "- 不能与源字段同名(避免 source/derived 重名)\n"
                        "- 支持 YAML anchor 复用"
                    ),
                    # `c15-yaml-dsl-demand-imports-scope`: `fields` 属于稳定编写入口之一, 允许 `$import`。
                    "properties": {_IMPORT_KEY: copy.deepcopy(types_mod.IMPORT_REF_SCHEMA)},
                    "propertyNames": {"anyOf": [{"const": _IMPORT_KEY}, schema_constants.FIELD_ID_STRING_SCHEMA]},
                    "additionalProperties": {"$ref": "#/definitions/field"},
                }
                continue
            ordered[name] = base_properties[name]
        return ordered

    def _build_field_definition(self) -> Dict[str, Any]:
        types_mod = self._types
        source_props = self._build_class_properties(types_mod.SourceFieldConfig, allow_import=True)
        derived_props = self._build_class_properties(types_mod.DerivedFieldConfig, allow_import=True)

        properties = dict(source_props)
        for name, schema in derived_props.items():
            if name in properties:
                if properties[name] != schema:
                    msg = "Field schema mismatch for '{}'".format(name)
                    raise ValueError(msg)
                continue
            properties[name] = schema

        properties.setdefault(_IMPORT_KEY, copy.deepcopy(types_mod.IMPORT_REF_SCHEMA))

        return {
            "type": "object",
            "additionalProperties": True,
            "properties": properties,
            "allOf": copy.deepcopy(types_mod.FIELD_DERIVED_CONDITIONS),
        }

    def _build_class_properties(self, cls: type, *, allow_import: bool) -> Dict[str, Any]:
        types_mod = self._types
        properties: Dict[str, Any] = {}
        for dc_field in dataclass_fields(cls):
            if dc_field.metadata.get(types_mod.SCHEMA_OMIT_KEY):
                continue
            meta = SchemaMeta.from_field(dc_field)
            prop_name = meta.schema_name or dc_field.name
            properties[prop_name] = self._build_field_schema(cls, dc_field, meta, allow_import=allow_import)
        return properties

    def _build_field_schema(self, owner_cls: type, dc_field: "Field[Any]", meta: SchemaMeta, *, allow_import: bool) -> Dict[str, Any]:
        context = "{}.{}".format(owner_cls.__name__, meta.schema_name or dc_field.name)
        meta_payload = dict(meta.meta)
        if "ref" in meta_payload:
            ref_name = meta_payload.pop("ref")
            if not meta_payload:
                return {"$ref": "#/definitions/{}".format(ref_name)}
            expanded = self._expand_meta(meta_payload)
            expanded["allOf"] = [{"$ref": "#/definitions/{}".format(ref_name)}]
            self._assert_numeric_constraints_typed(expanded, context=context)
            return expanded
        if "schema" in meta_payload:
            schema = cast("Dict[str, Any]", copy.deepcopy(meta_payload.pop("schema")))  # pragma: allow-cast meta schema typed narrowing
            schema.update(self._expand_meta(meta_payload))
            self._assert_numeric_constraints_typed(schema, context=context)
            return schema

        schema = self._schema_for_type(dc_field.type, allow_import=allow_import)
        schema.update(self._expand_meta(meta_payload))
        self._assert_numeric_constraints_typed(schema, context=context)
        return schema

    def _assert_numeric_constraints_typed(self, schema: Dict[str, Any], *, context: str) -> None:
        constraint_keys = self.NUMERIC_CONSTRAINT_KEYS.intersection(schema)
        if not constraint_keys:
            return

        raw_type = cast("object", schema.get("type"))  # pragma: allow-cast jsonschema `type` can be scalar/list
        types: List[str] = []
        if isinstance(raw_type, str):
            types = [raw_type]
        elif isinstance(raw_type, list):
            for item in cast("List[Any]", raw_type):  # pragma: allow-cast jsonschema list typed narrowing
                if isinstance(item, str):
                    types.append(item)

        if any(item in self.NUMERIC_SCHEMA_TYPES for item in types):
            return

        msg = "Invalid schema: numeric constraints {} require explicit numeric type for {}; got type={}".format(
            ",".join(sorted(constraint_keys)),
            context,
            repr(cast("object", raw_type)),  # pragma: allow-cast repr accepts any object
        )
        raise ValueError(msg)

    def _assert_schema_does_not_expose_import_key(self, value: Any, *, path: str) -> None:
        if isinstance(value, dict):
            typed = cast("Dict[str, Any]", value)  # pragma: allow-cast schema traversal typed narrowing
            if _IMPORT_KEY in typed:
                msg = "Workflow schema MUST NOT expose {!r} (found at {})".format(_IMPORT_KEY, path)
                raise ValueError(msg)
            for key, item in typed.items():
                self._assert_schema_does_not_expose_import_key(item, path="{}.{}".format(path, key))
            return
        if isinstance(value, list):
            items = cast("List[Any]", value)  # pragma: allow-cast schema traversal typed narrowing
            for idx, item in enumerate(items):
                self._assert_schema_does_not_expose_import_key(item, path="{}[{}]".format(path, idx))
            return

    def schemas_equivalent(self, left: Any, right: Any) -> bool:
        return self.normalize_schema(left) == self.normalize_schema(right)

    def normalize_schema(self, value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            typed = cast("Dict[str, Any]", value)  # pragma: allow-cast yaml mapping typed narrowing
            return {k: self.normalize_schema(v, k) for k, v in typed.items() if k not in self.IGNORED_KEYS}
        if isinstance(value, list):
            items = cast("List[Any]", value)  # pragma: allow-cast yaml list typed narrowing
            normalized = [self.normalize_schema(item) for item in items]
            if key in self.ORDER_INSENSITIVE_KEYS:
                return sorted(normalized, key=self._sort_key)
            return normalized
        if isinstance(value, tuple):
            items = cast("Tuple[Any, ...]", value)  # pragma: allow-cast yaml tuple typed narrowing
            return self.normalize_schema(list(items), key)
        return value

    def _sort_key(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def _expand_meta(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        expanded: Dict[str, Any] = {}
        items_choices = None
        for key, value in meta.items():
            mapped_key = self.META_KEY_MAP.get(key, key)
            if mapped_key == "additionalProperties":
                expanded[mapped_key] = self._expand_additional_props(value)
            elif mapped_key == "items_choices":
                items_choices = value
            else:
                expanded[mapped_key] = copy.deepcopy(value)

        if items_choices is not None:
            if "items" not in expanded:
                expanded["items"] = {}
            if isinstance(expanded["items"], dict):
                items_schema = cast("Dict[str, Any]", expanded["items"])  # pragma: allow-cast schema expansion typed narrowing
                items_schema["enum"] = copy.deepcopy(items_choices)

        if "examples" in expanded and not isinstance(expanded["examples"], list):
            expanded["examples"] = [expanded["examples"]]
        if "markdownDescription" not in expanded and "description" in expanded:
            expanded["markdownDescription"] = expanded["description"]

        return expanded

    def _expand_additional_props(self, value: Any) -> Any:
        if isinstance(value, str):
            return {"$ref": "#/definitions/{}".format(value)}
        return copy.deepcopy(value)

    def _schema_for_type(self, tp: Any, *, allow_import: bool) -> Dict[str, Any]:
        tp = self._strip_optional(tp)
        origin = getattr(tp, "__origin__", None)  # pragma: allow-dynattr introspection: __origin__
        primitive = self._primitive_schema(tp)
        if primitive:
            return primitive

        container = self._container_schema(tp, origin, allow_import=allow_import)
        if container:
            return container

        ref_schema = self._ref_schema(tp)
        if ref_schema:
            return ref_schema

        return {}

    def _strip_optional(self, tp: Any) -> Any:
        origin = getattr(tp, "__origin__", None)  # pragma: allow-dynattr introspection: __origin__
        if origin is Union:
            args = [arg for arg in getattr(tp, "__args__", ()) if arg is not type(None)]  # pragma: allow-dynattr introspection: __args__
            if len(args) == 1:
                return args[0]
        return tp

    def _primitive_schema(self, tp: Any) -> Dict[str, Any]:
        if isinstance(tp, type) and tp in self.PRIMITIVE_TYPE_MAP:
            return {"type": self.PRIMITIVE_TYPE_MAP[tp]}
        return {}

    def _container_schema(self, tp: Any, origin: Any, *, allow_import: bool) -> Dict[str, Any]:
        types_mod = self._types

        if origin is list or tp is list:
            args = getattr(tp, "__args__", ())  # pragma: allow-dynattr introspection: __args__
            item_type = args[0] if args else object
            return {"type": "array", "items": self._schema_for_type(item_type, allow_import=allow_import)}

        if origin is dict or tp is dict:
            if allow_import:
                return {"type": "object", "properties": {_IMPORT_KEY: copy.deepcopy(types_mod.IMPORT_REF_SCHEMA)}}
            return {"type": "object"}

        if origin is tuple or tp is tuple:
            return self._tuple_schema(tp, allow_import=allow_import)

        return {}

    def _tuple_schema(self, tp: Any, *, allow_import: bool) -> Dict[str, Any]:
        raw_args = getattr(tp, "__args__", ())  # pragma: allow-dynattr introspection: __args__
        args = cast("Tuple[Any, ...]", raw_args)  # pragma: allow-cast typing args typed narrowing
        if len(args) == self.ELLIPSIS_TUPLE_LEN and args[1] is Ellipsis:
            return {"type": "array", "items": self._schema_for_type(args[0], allow_import=allow_import)}

        if args:
            items = [self._schema_for_type(arg, allow_import=allow_import) for arg in args]
            return {
                "type": "array",
                "items": items,
                "minItems": len(items),
                "maxItems": len(items),
                "additionalItems": False,
            }

        return {"type": "array"}

    def _ref_schema(self, tp: Any) -> Dict[str, Any]:
        if isinstance(tp, type):
            schema_name = getattr(tp, "SCHEMA_NAME", None)  # pragma: allow-dynattr metadata: schema meta
            if isinstance(schema_name, str):
                return {"$ref": "#/definitions/{}".format(schema_name)}
        return {}


_DEFAULT_BUILDER = SchemaBuilder()


def build_demand_schema() -> Dict[str, Any]:
    return _DEFAULT_BUILDER.build_demand_schema()


def build_workflow_schema() -> Dict[str, Any]:
    return _DEFAULT_BUILDER.build_workflow_schema()


def build_scalim_yaml_schema() -> Dict[str, Any]:
    return _DEFAULT_BUILDER.build_scalim_yaml_schema()


def load_schema(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_demand_schema(output_path: Path) -> None:
    schema = build_demand_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, sort_keys=False)
        _ = handle.write("\n")


def write_workflow_schema(output_path: Path) -> None:
    schema = build_workflow_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, sort_keys=False)
        _ = handle.write("\n")


def write_scalim_yaml_schema(output_path: Path) -> None:
    schema = build_scalim_yaml_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, sort_keys=False)
        _ = handle.write("\n")


def schemas_equivalent(left: Any, right: Any) -> bool:
    return _DEFAULT_BUILDER.schemas_equivalent(left, right)


def normalize_schema(value: Any, key: str = "") -> Any:
    return _DEFAULT_BUILDER.normalize_schema(value, key)


__all__ = ()
