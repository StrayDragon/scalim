from typing import Any, Dict


def build_workflow_cache_pool_pin_item_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "required": ["kind", "source_id"],
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["preload_forever"],
                "description": "pin kind(v0 仅允许 preload_forever)",
                "markdownDescription": "pin kind.\n\n- `preload_forever`: pin 该 `(kind, source_id)` 的缓存(避免被 refcount/LRU 逐出)",
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


def build_workflow_cache_pool_schema() -> Dict[str, Any]:
    pin_item = build_workflow_cache_pool_pin_item_schema()
    return {
        "type": "object",
        "required": ["conflict_policy", "release_policy", "budget"],
        "properties": {
            "conflict_policy": {
                "type": "string",
                "enum": ["error", "separate", "warn"],
                "description": "signature 冲突策略(error/separate/warn)",
                "markdownDescription": (
                    "signature 冲突策略.\n\n"
                    "- `error`: 发现同一 `(kind, source_id)` 的 signature 不一致时直接失败\n"
                    "- `warn`: 允许冲突并继续(会发出 warning 事件,并附带 diff 摘要)\n"
                    "- `separate`: 允许冲突并继续(作为独立 entry 共存;当前实现与 warn 等价,仍会发 warning)"
                ),
            },
            "release_policy": {
                "type": "string",
                "enum": ["dag_refcount", "workflow_end"],
                "description": "释放策略(dag_refcount/workflow_end)",
                "markdownDescription": (
                    "释放策略.\n\n"
                    "- `dag_refcount`: 当某 `(kind, source_id)` 的剩余 consumer=0 时释放(类似 DAG 引用计数)\n"
                    "- `workflow_end`: 直到 workflow 结束才释放(占用更久,但可能减少重复加载)"
                ),
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
                        "markdownDescription": (
                            "超限策略.\n\n"
                            "- `fail_fast`: 超限即失败\n"
                            "- `evict_lru`: 逐出 LRU 的 idle entry(仅逐出 refcount=0 且非 pin); 若无可逐出项则失败"
                        ),
                    },
                },
                "additionalProperties": False,
            },
            "pin": {
                "type": "array",
                "items": pin_item,
                "default": [],
                "description": "pin 列表(可选)",
                "markdownDescription": "pin 列表(可选).",
            },
        },
        "additionalProperties": False,
    }


def build_workflow_options_schema() -> Dict[str, Any]:
    cache_pool = build_workflow_cache_pool_schema()
    return {
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
                "markdownDescription": "失败策略.\n\n- `all_fail`: 任一 run 失败即失败\n- `primary_only`: 失败 run 被跳过但 workflow 继续",
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


def build_workflow_run_item_schema() -> Dict[str, Any]:
    return {
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
        },
        "additionalProperties": False,
    }


def build_workflow_workflow_schema() -> Dict[str, Any]:
    run_item = build_workflow_run_item_schema()
    options = build_workflow_options_schema()
    return {
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
                "allOf": [{"$ref": "#/definitions/resources"}],
                "default": {},
                "description": "workflow-scope shared IO resources",
                "markdownDescription": (
                    "workflow-scope shared IO resources.\n\n- stable surface: `workflow.resources.books` / `workflow.resources.files`"
                ),
            },
        },
        "additionalProperties": False,
    }


__all__ = ()
