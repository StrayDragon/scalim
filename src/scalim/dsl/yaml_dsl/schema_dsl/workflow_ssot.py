from typing import Any, Dict


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
    return {
        "type": "object",
        "required": ["runs"],
        "properties": {
            "runs": {
                "type": "array",
                "minItems": 1,
                "items": run_item,
            },
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
