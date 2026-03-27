import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple, Type, Union, cast

from ....vendor.dataclassesx import Field, dataclass
from ....vendor.dataclassesx import fields as dataclass_fields
from . import constants as schema_constants
from . import models as schema_models
from .constants import SCHEMA_META_KEY

_IMPORT_KEY = "$import"
_IMPORTS_KEY = "imports"


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
        str: "string",
    }
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
            "output_container": self._build_definition(types_mod.OutputContainerConfig),
            "output_aggregate": self._build_definition(types_mod.OutputAggregateConfig),
            "output_target": self._build_definition(types_mod.OutputTargetConfig),
            "output_extra_sheet": self._build_definition(types_mod.OutputExtraSheetConfig),
            "logging": self._build_definition(types_mod.LoggingConfig),
            "performance_thresholds": self._build_definition(types_mod.PerformanceThresholdsConfig),
            "performance_report": self._build_definition(types_mod.PerformanceReportConfig),
            "performance": self._build_definition(types_mod.PerformanceConfig),
            "relation_report": self._build_definition(types_mod.RelationReportConfig),
            "relations": self._build_definition(types_mod.RelationsConfig),
            "viz": self._build_definition(types_mod.VizConfig),
            "trace": self._build_definition(types_mod.TraceConfig),
            "row_gap": self._build_definition(types_mod.RowGapConfig),
            "memory_opt": self._build_definition(types_mod.MemoryOptimizationConfig),
            "observability": self._build_definition(types_mod.ObservabilityConfig),
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
            # `$import` 会在编译期展开;为提升 `LSP`/`schema` 体验,允许仅声明 `$import` 的用法通过校验.
            "anyOf": [{"required": list(types_mod.DEMAND_SCHEMA_REQUIRED)}, {"required": [_IMPORT_KEY]}],
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
        return schema

    def build_workflow_schema(self) -> Dict[str, Any]:
        types_mod = self._types
        cache_pool_pin_item: Dict[str, Any] = {
            "type": "object",
            "required": ["kind", "source_id"],
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["preload_forever"],
                    "description": "pin kind(v0 仅允许 preload_forever)",
                    "markdownDescription": "pin kind(v0 仅允许 `preload_forever`).",
                },
                "source_id": {
                    "type": "string",
                    "minLength": 1,
                    "description": "pin 的 source_id",
                    "markdownDescription": "pin 的 `source_id`.",
                },
            },
            "additionalProperties": False,
        }

        cache_pool: Dict[str, Any] = {
            "type": "object",
            "required": ["conflict_policy", "release_policy", "budget"],
            "properties": {
                "conflict_policy": {
                    "type": "string",
                    "enum": ["error", "separate", "warn"],
                    "description": "signature 冲突策略(error/separate/warn)",
                    "markdownDescription": "signature 冲突策略(`error`/`separate`/`warn`).",
                },
                "release_policy": {
                    "type": "string",
                    "enum": ["dag_refcount", "workflow_end"],
                    "description": "释放策略(dag_refcount/workflow_end)",
                    "markdownDescription": "释放策略(`dag_refcount`/`workflow_end`).",
                },
                "budget": {
                    "type": "object",
                    "required": ["max_entries", "over_budget_policy"],
                    "properties": {
                        "max_entries": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "cache pool entry 数量预算(>=1)",
                            "markdownDescription": "cache pool entry 数量预算(>=1).",
                        },
                        "over_budget_policy": {
                            "type": "string",
                            "enum": ["fail_fast", "evict_lru"],
                            "description": "超限策略(fail_fast/evict_lru)",
                            "markdownDescription": "超限策略(`fail_fast`/`evict_lru`).",
                        },
                    },
                    "additionalProperties": False,
                },
                "pin": {
                    "type": "array",
                    "items": cache_pool_pin_item,
                    "default": [],
                    "description": "pin 列表(可选)",
                    "markdownDescription": "pin 列表(可选).",
                },
            },
            "additionalProperties": False,
        }

        options: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "max_concurrency": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": "runs 粒度并发上限(>=1)",
                    "markdownDescription": "runs 粒度并发上限(>=1).",
                },
                "failure_policy": {
                    "type": "string",
                    "enum": ["all_fail", "primary_only"],
                    "default": "all_fail",
                    "description": "失败策略(all_fail/primary_only)",
                    "markdownDescription": (
                        "失败策略.\n\n- `all_fail`: 任一 run 失败即失败\n- `primary_only`: 失败 run 被跳过但 workflow 继续"
                    ),
                },
                "cache_pool": {
                    "oneOf": [cache_pool, {"type": "null"}],
                    "default": None,
                    "description": "workflow-scope cache pool 配置(可选)",
                    "markdownDescription": "workflow-scope cache pool 配置(可选).",
                },
                "ctx": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "max_value_bytes": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "default": 65536,
                                    "description": "ctx 单 key 最大字节数(>=1)",
                                    "markdownDescription": "ctx 单 key 最大字节数(>=1).",
                                },
                                "max_bytes": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "default": 1048576,
                                    "description": "ctx 总量最大字节数(>=1)",
                                    "markdownDescription": "ctx 总量最大字节数(>=1).",
                                },
                            },
                            "additionalProperties": False,
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                    "description": "workflow-level ctx 护栏配置(可选)",
                    "markdownDescription": "workflow-level ctx 护栏配置(可选).",
                },
            },
            "additionalProperties": False,
        }

        workbook_resource: Dict[str, Any] = {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "workbook 输出路径(非空字符串)",
                    "markdownDescription": "workbook 输出路径(非空字符串).",
                    "examples": ["./out/report.xlsx"],
                },
                "allow_formulas": {
                    "type": "boolean",
                    "default": False,
                    "description": "允许公式(可信输入显式放宽,将禁用公式前缀转义)",
                    "markdownDescription": "允许公式(可信输入显式放宽,将禁用公式前缀转义).",
                    "examples": [True],
                },
            },
            "additionalProperties": False,
        }

        csv_resource: Dict[str, Any] = {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "csv 输出路径(非空字符串)",
                    "markdownDescription": "csv 输出路径(非空字符串).",
                    "examples": ["./out/report.csv"],
                }
            },
            "additionalProperties": False,
        }

        write_to_workbook_sheet: Dict[str, Any] = {
            "type": "object",
            "required": ["workbook", "sheet", "output"],
            "properties": {
                "workbook": {"type": "string", "minLength": 1},
                "sheet": {"type": "string", "minLength": 1},
                "output": {"type": "string", "minLength": 1},
                "on_conflict": {
                    "type": "string",
                    "enum": ["error", "overwrite", "skip"],
                    "default": "error",
                },
            },
            "additionalProperties": False,
        }

        write_to_workbook_append: Dict[str, Any] = {
            "type": "object",
            "required": ["workbook", "sheet", "output"],
            "properties": {
                "workbook": {"type": "string", "minLength": 1},
                "sheet": {"type": "string", "minLength": 1},
                "output": {"type": "string", "minLength": 1},
                "align_by": {
                    "type": "string",
                    "enum": ["field_id", "header"],
                    "default": "field_id",
                },
                "header_policy": {
                    "type": "string",
                    "enum": ["once", "always", "never"],
                    "default": "once",
                },
                "on_mismatch": {
                    "type": "string",
                    "enum": ["error", "warn", "skip"],
                    "default": "error",
                },
            },
            "additionalProperties": False,
        }

        write_to_csv_append: Dict[str, Any] = {
            "type": "object",
            "required": ["csv", "output"],
            "properties": {
                "csv": {"type": "string", "minLength": 1},
                "output": {"type": "string", "minLength": 1},
                "header_policy": {
                    "type": "string",
                    "enum": ["once", "always", "never"],
                    "default": "once",
                },
                "on_mismatch": {
                    "type": "string",
                    "enum": ["error", "warn", "skip"],
                    "default": "error",
                },
            },
            "additionalProperties": False,
        }

        sheetbook_budget: Dict[str, Any] = {
            "type": "object",
            "required": ["max_sheets", "max_total_cells"],
            "properties": {
                "max_sheets": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "sheetbook budget: max_sheets(正整数)",
                    "markdownDescription": "sheetbook budget: `max_sheets`(正整数).",
                    "examples": [32],
                },
                "max_total_cells": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "sheetbook budget: max_total_cells(正整数)",
                    "markdownDescription": "sheetbook budget: `max_total_cells`(正整数).",
                    "examples": [5000000],
                },
            },
            "additionalProperties": False,
        }

        sheetbook_export_xlsx: Dict[str, Any] = {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "导出 xlsx 路径(非空字符串)",
                    "markdownDescription": "导出 xlsx 路径(非空字符串).",
                    "examples": ["./out/report.xlsx"],
                },
                "write_lock": {
                    "type": "boolean",
                    "default": False,
                    "description": "导出阶段启用写锁(可选)",
                    "markdownDescription": "导出阶段启用写锁(可选).",
                    "examples": [True],
                },
                "allow_formulas": {
                    "type": "boolean",
                    "default": False,
                    "description": "允许公式(可信输入显式放宽,将禁用公式前缀转义)",
                    "markdownDescription": "允许公式(可信输入显式放宽,将禁用公式前缀转义).",
                    "examples": [True],
                },
            },
            "additionalProperties": False,
        }

        sheetbook_resource: Dict[str, Any] = {
            "type": "object",
            "required": ["budget"],
            "properties": {
                "budget": sheetbook_budget,
                "export_xlsx": sheetbook_export_xlsx,
            },
            "additionalProperties": False,
        }

        write_to_sheetbook_sheet: Dict[str, Any] = {
            "type": "object",
            "required": ["sheetbook", "sheet", "output"],
            "properties": {
                "sheetbook": {"type": "string", "minLength": 1},
                "sheet": {"type": "string", "minLength": 1},
                "output": {"type": "string", "minLength": 1},
                "on_conflict": {
                    "type": "string",
                    "enum": ["error", "overwrite", "skip"],
                    "default": "error",
                },
            },
            "additionalProperties": False,
        }

        write_to_sheetbook_append: Dict[str, Any] = {
            "type": "object",
            "required": ["sheetbook", "sheet", "output"],
            "properties": {
                "sheetbook": {"type": "string", "minLength": 1},
                "sheet": {"type": "string", "minLength": 1},
                "output": {"type": "string", "minLength": 1},
                "align_by": {
                    "type": "string",
                    "enum": ["field_id", "header"],
                    "default": "field_id",
                },
                "header_policy": {
                    "type": "string",
                    "enum": ["once", "always", "never"],
                    "default": "once",
                },
                "on_mismatch": {
                    "type": "string",
                    "enum": ["error", "warn", "skip"],
                    "default": "error",
                },
            },
            "additionalProperties": False,
        }

        write_intent_item: Dict[str, Any] = {
            "oneOf": [
                {
                    "type": "object",
                    "required": ["workbook_sheet"],
                    "properties": {"workbook_sheet": write_to_workbook_sheet},
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["workbook_append"],
                    "properties": {"workbook_append": write_to_workbook_append},
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["csv_append"],
                    "properties": {"csv_append": write_to_csv_append},
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["sheetbook_sheet"],
                    "properties": {"sheetbook_sheet": write_to_sheetbook_sheet},
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["sheetbook_append"],
                    "properties": {"sheetbook_append": write_to_sheetbook_append},
                    "additionalProperties": False,
                },
            ],
            "description": "写入意图单条声明(item 必须恰好选择一个 intent key)",
            "markdownDescription": "写入意图单条声明.\n\n- item MUST 恰好选择一个 intent key",
        }

        writes: Dict[str, Any] = {
            "type": "array",
            "items": write_intent_item,
            "default": [],
            "description": "共享输出写入意图列表(可选)",
            "markdownDescription": (
                "共享输出写入意图列表(可选).\n\n"
                "- 缺省/空数组表示无写入意图\n"
                "- 每个 item MUST 恰好选择一个 write intent\n"
                "- 写入顺序 SSOT: run 顺序 + writes 顺序"
            ),
        }

        run_item: Dict[str, Any] = {
            "type": "object",
            "required": ["id", "demand"],
            "properties": {
                "id": {
                    "type": "string",
                    "minLength": 1,
                    "description": "run 标识(非空且唯一)",
                    "markdownDescription": "run 标识(非空且唯一).",
                },
                "demand": {
                    "type": "string",
                    "minLength": 1,
                    "description": "demand YAML 路径(字符串)",
                    "markdownDescription": (
                        "demand YAML 路径(字符串).\n\n"
                        "- 相对路径以 workflow 文件所在目录为基准\n"
                        "- 可通过 Python 入口注入 path_aliases 解析 `@/...` 或 `ALIAS:/...`"
                    ),
                },
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "default": [],
                    "description": "显式依赖 run.id 列表(可选)",
                    "markdownDescription": "显式依赖 `run.id` 列表(可选).",
                },
                "main_rows_from": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["run"],
                            "properties": {
                                "run": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "上游 run.id(作为本 run 的 main_rows 输入)",
                                    "markdownDescription": "上游 `run.id`(producer).",
                                }
                            },
                            "additionalProperties": False,
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                    "description": "可选:将上游 typed rows 作为本 run 的 main_rows 输入",
                    "markdownDescription": (
                        "可选:将上游 `InMemoryRows`(typed rows) 作为本 run 的 `main_rows` 输入.\n\n"
                        "- MUST 显式声明 `depends_on` 该上游 run\n"
                        "- producer 仅在被引用时才会启用 typed rows 捕获"
                    ),
                },
                "init_vars": {
                    "oneOf": [
                        {
                            "type": "object",
                            "propertyNames": {"type": "string", "minLength": 1},
                            "additionalProperties": True,
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                    "description": "demand compile-time init_vars(可选,支持 $ctx 指令)",
                    "markdownDescription": "demand compile-time `init_vars`(可选,支持 `$ctx` 指令).",
                },
                "writes": writes,
            },
            "additionalProperties": False,
        }

        workflow: Dict[str, Any] = {
            "type": "object",
            "required": ["runs"],
            "properties": {
                "runs": {
                    "type": "array",
                    "minItems": 1,
                    "items": run_item,
                },
                "options": options,
                "resources": {
                    "type": "object",
                    "properties": {
                        "workbooks": {
                            "type": "object",
                            "default": {},
                            "propertyNames": {"type": "string", "minLength": 1},
                            "additionalProperties": workbook_resource,
                        },
                        "csvs": {
                            "type": "object",
                            "default": {},
                            "propertyNames": {"type": "string", "minLength": 1},
                            "additionalProperties": csv_resource,
                        },
                        "sheetbooks": {
                            "type": "object",
                            "default": {},
                            "propertyNames": {"type": "string", "minLength": 1},
                            "additionalProperties": sheetbook_resource,
                        },
                    },
                    "description": "workflow-scope shared output resources",
                    "markdownDescription": "workflow-scope shared output resources.",
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }

        schema: Dict[str, Any] = {
            "$schema": types_mod.DEMAND_SCHEMA_META["$schema"],
            "$id": "https://scalim.example.com/schemas/workflow.json",
            "title": "Scalim Workflow 配置",
            "description": "Scalim 框架 workflow YAML 配置定义 Schema",
            "$comment": self.GENERATED_SCHEMA_COMMENT,
            "type": "object",
            "required": ["workflow"],
            "properties": {"workflow": workflow},
            "additionalProperties": False,
        }
        return schema

    def _import_ref_schema(self) -> Dict[str, Any]:
        return {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}, "minItems": 1},
            ],
            "description": "$import 引用(支持 string 或 string list)",
            "markdownDescription": (
                "$import 引用.\n\n"
                "- string: `<alias>(.<segment>)*`\n"
                "- list: 按顺序合并,后者覆盖前者,最终再被本地覆盖\n"
                "- 仅支持 mapping 片段\n"
                "- V1 仅支持同级文件导入(见顶层 `imports`)"
            ),
            "examples": ["common.sources", ["common.sources", "other.sources"]],
        }

    def _imports_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "description": "片段文件导入别名映射(编译期展开)",
            "markdownDescription": (
                "片段文件导入别名映射.\n\n"
                "- key: alias\n"
                "- value: 片段文件路径(字符串)\n"
                "- V2 支持相对路径 fragments(解析基准: 当前 YAML 文件所在目录):\n"
                "  - `./x.yaml` / `x.yaml`\n"
                "  - `x/y.yaml`(子目录)\n"
                "  - `../x.yaml`(父目录)\n"
                "- 支持(编辑器侧放宽,运行时校验为准):\n"
                "  - alias 路径: `@/x.yaml`, `COMMON:/x.yaml`(需 `scalim.yaml` 显式配置)\n"
                "  - 内置 preset: `scalim://yaml-dsl/presets/common.yaml`(仅本地白名单)\n"
                "- 禁止(以运行时为准): 绝对路径/非 `scalim://` 的 `URI scheme`/Windows 盘符/反斜杠分隔符等"
            ),
            "propertyNames": {"type": "string", "pattern": r"^[a-zA-Z_][a-zA-Z0-9_]*$"},
            "additionalProperties": {
                "type": "string",
                # 说明: 更严格的边界与诊断以运行时实现为准(例如拒绝 `URI scheme`/绝对路径).
                "pattern": (
                    r"^("
                    r"(\./|\.\./)*([^/\\:]+/)*[^/\\:]+\.ya?ml"
                    r"|@/([^/\\:]+/)*[^/\\:]+\.ya?ml"
                    r"|[a-zA-Z_][a-zA-Z0-9_]*:/([^/\\:]+/)*[^/\\:]+\.ya?ml"
                    r"|scalim://[^\\s\\\\]+\.ya?ml"
                    r")$"
                ),
            },
        }

    def _build_definition(self, cls: type) -> Dict[str, Any]:
        properties = self._build_class_properties(cls)
        properties.setdefault(_IMPORT_KEY, self._import_ref_schema())
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }

        required = getattr(cls, "SCHEMA_REQUIRED", ())  # pragma: allow-dynattr metadata: schema meta
        if required:
            # `$import` 会在编译期展开;为提升 `LSP`/`schema` 体验,允许仅声明 `$import` 的用法通过校验.
            schema["anyOf"] = [{"required": list(required)}, {"required": [_IMPORT_KEY]}]

        additional_props = getattr(cls, "SCHEMA_ADDITIONAL_PROPERTIES", None)  # pragma: allow-dynattr metadata: schema meta
        if additional_props is not None:
            schema["additionalProperties"] = bool(additional_props)

        all_of = getattr(cls, "SCHEMA_ALL_OF", None)  # pragma: allow-dynattr metadata: schema meta
        if all_of is not None:
            schema["allOf"] = copy.deepcopy(all_of)

        return schema

    def _build_demand_properties(self) -> Dict[str, Any]:
        types_mod = self._types
        base_properties = self._build_class_properties(types_mod.DemandConfig)
        base_properties.setdefault(_IMPORTS_KEY, self._imports_schema())
        base_properties.setdefault(_IMPORT_KEY, self._import_ref_schema())
        ordered: Dict[str, Any] = {}
        for name in types_mod.DEMAND_SCHEMA_PROPERTIES_ORDER:
            if name == "_templates":
                ordered[name] = {
                    "type": "object",
                    "description": "YAML anchor 模板集合(_templates), 供 fields/relations 复用",
                    "markdownDescription": (
                        "YAML anchor 模板集合.\n\n- 仅用于 YAML 复用(anchors)\n- 常用于 `fields` / `relations` / `retry`"
                    ),
                    "properties": {
                        "retry": {
                            "type": "object",
                            "description": "可复用的 retry 策略模板集合",
                            "markdownDescription": "可复用的 retry 策略模板集合.\n\n- key 为模板名\n- value 为 retry policy 对象",
                            "additionalProperties": {"$ref": "#/definitions/loader_retry"},
                        }
                    },
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
                    "additionalProperties": {"$ref": "#/definitions/field"},
                }
                continue
            ordered[name] = base_properties[name]
        return ordered

    def _build_field_definition(self) -> Dict[str, Any]:
        types_mod = self._types
        source_props = self._build_class_properties(types_mod.SourceFieldConfig)
        derived_props = self._build_class_properties(types_mod.DerivedFieldConfig)

        properties = dict(source_props)
        for name, schema in derived_props.items():
            if name in properties:
                if properties[name] != schema:
                    msg = "Field schema mismatch for '{}'".format(name)
                    raise ValueError(msg)
                continue
            properties[name] = schema

        properties.setdefault(_IMPORT_KEY, self._import_ref_schema())

        return {
            "type": "object",
            "additionalProperties": True,
            "properties": properties,
            "allOf": copy.deepcopy(types_mod.FIELD_DERIVED_CONDITIONS),
        }

    def _build_class_properties(self, cls: type) -> Dict[str, Any]:
        types_mod = self._types
        properties: Dict[str, Any] = {}
        for dc_field in dataclass_fields(cls):
            if dc_field.metadata.get(types_mod.SCHEMA_OMIT_KEY):
                continue
            meta = SchemaMeta.from_field(dc_field)
            prop_name = meta.schema_name or dc_field.name
            properties[prop_name] = self._build_field_schema(dc_field, meta)
        return properties

    def _build_field_schema(self, dc_field: "Field[Any]", meta: SchemaMeta) -> Dict[str, Any]:
        meta_payload = dict(meta.meta)
        if "ref" in meta_payload:
            ref_name = meta_payload.pop("ref")
            if not meta_payload:
                return {"$ref": "#/definitions/{}".format(ref_name)}
            expanded = self._expand_meta(meta_payload)
            expanded["allOf"] = [{"$ref": "#/definitions/{}".format(ref_name)}]
            return expanded
        if "schema" in meta_payload:
            schema = cast("Dict[str, Any]", copy.deepcopy(meta_payload.pop("schema")))  # pragma: allow-cast meta schema typed narrowing
            schema.update(self._expand_meta(meta_payload))
            return schema

        schema = self._schema_for_type(dc_field.type)
        schema.update(self._expand_meta(meta_payload))
        return schema

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

    def _schema_for_type(self, tp: Any) -> Dict[str, Any]:
        tp = self._strip_optional(tp)
        origin = getattr(tp, "__origin__", None)  # pragma: allow-dynattr introspection: __origin__
        primitive = self._primitive_schema(tp)
        if primitive:
            return primitive

        container = self._container_schema(tp, origin)
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

    def _container_schema(self, tp: Any, origin: Any) -> Dict[str, Any]:
        if origin is list or tp is list:
            args = getattr(tp, "__args__", ())  # pragma: allow-dynattr introspection: __args__
            item_type = args[0] if args else object
            return {"type": "array", "items": self._schema_for_type(item_type)}

        if origin is dict or tp is dict:
            return {"type": "object", "properties": {_IMPORT_KEY: self._import_ref_schema()}}

        if origin is tuple or tp is tuple:
            return self._tuple_schema(tp)

        return {}

    def _tuple_schema(self, tp: Any) -> Dict[str, Any]:
        raw_args = getattr(tp, "__args__", ())  # pragma: allow-dynattr introspection: __args__
        args = cast("Tuple[Any, ...]", raw_args)  # pragma: allow-cast typing args typed narrowing
        if len(args) == self.ELLIPSIS_TUPLE_LEN and args[1] is Ellipsis:
            return {"type": "array", "items": self._schema_for_type(args[0])}

        if args:
            items = [self._schema_for_type(arg) for arg in args]
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


def schemas_equivalent(left: Any, right: Any) -> bool:
    return _DEFAULT_BUILDER.schemas_equivalent(left, right)


def normalize_schema(value: Any, key: str = "") -> Any:
    return _DEFAULT_BUILDER.normalize_schema(value, key)


__all__ = []
