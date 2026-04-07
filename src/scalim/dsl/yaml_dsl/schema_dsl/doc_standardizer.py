# pragma: allow-cast-file gen-only schema doc standardizer; casts for Any-narrowing (not runtime hot path)
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....vendor.yamlx import yaml

_IMPORT_KEY = "$import"
_DOC_LEVEL_FULL_MIN_NON_EMPTY_LINES = 8
_DOC_LEVEL_BRIEF_IMPORT_MAX_LINES = 3
_NULLABLE_UNION_OPTION_COUNT = 2

_BEGIN_SNIPPET_RE = re.compile(r"^\s*#\s*<!--\s*BEGIN\s+AUTOGEN:(?P<id>[^\s>]+)\s*-->\s*$")
_END_SNIPPET_RE = re.compile(r"^\s*#\s*<!--\s*END\s+AUTOGEN:(?P<id>[^\s>]+)\s*-->\s*$")


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _first_non_empty_lines(text: str, *, max_lines: int = 3) -> str:
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        lines.append(line)
        if len(lines) >= max_lines:
            break
    return "\n".join(lines).strip()


def _yaml_dump(value: Any) -> str:
    dumped = yaml.safe_dump(value, allow_unicode=True, default_flow_style=False, sort_keys=True)
    # NOTE: 标量 YAML 序列化可能带 `...` 结束标记;对片段示例无意义,且会引入悬停提示噪音.
    stripped = dumped.rstrip()
    if stripped.endswith("\n..."):
        stripped = stripped[: -len("\n...")]
    if stripped.endswith("..."):
        stripped = stripped[: -len("...")]
    return stripped.strip() + "\n"


def _as_dict(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return cast("Dict[str, Any]", value)
    return None


def _as_list(value: Any) -> Optional[List[Any]]:
    if isinstance(value, list):
        return cast("List[Any]", value)
    return None


def _as_str_list(value: Any) -> List[str]:
    raw = _as_list(value)
    if raw is not None:
        out: List[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
        return out
    return []


def _schema_types(node: Mapping[str, Any]) -> List[str]:
    raw = node.get("type")
    if isinstance(raw, str):
        return [raw]
    raw_list = _as_list(raw)
    if raw_list is not None:
        out: List[str] = []
        for item in raw_list:
            if isinstance(item, str):
                out.append(item)
        return out
    return []


def _is_container_schema(node: Mapping[str, Any]) -> bool:
    types = set(_schema_types(node))
    if "object" in types or "array" in types:
        return True
    return ("properties" in node) or ("items" in node) or ("additionalProperties" in node)


def _has_enum(node: Mapping[str, Any]) -> bool:
    if isinstance(node.get("enum"), list):
        return True
    items = _as_dict(node.get("items"))
    return items is not None and isinstance(items.get("enum"), list)


def _extract_ref_target(node: Mapping[str, Any]) -> Optional[str]:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/definitions/"):
        return ref.split("/")[-1]
    all_of = node.get("allOf")
    all_of_list = _as_list(all_of)
    if all_of_list is not None and len(all_of_list) == 1:
        only = _as_dict(all_of_list[0])
        if only is not None:
            return _extract_ref_target(only)
    return None


def _detect_import_required_workaround(node: Mapping[str, Any]) -> Optional[Set[str]]:  # noqa: PLR0911
    """识别 `builder._build_definition()` 的 `$import` 必填字段兜底规则.

    匹配模式: `anyOf` 中同时存在 `required=<core>` 与 `required=["$import"]` 两个分支.
    """

    any_of_list = _as_list(node.get("anyOf"))
    if any_of_list is None or len(any_of_list) != _NULLABLE_UNION_OPTION_COUNT:
        return None

    required_lists: List[List[str]] = []
    for item in any_of_list:
        item_dict = _as_dict(item)
        if item_dict is None:
            return None
        req_list = _as_list(item_dict.get("required"))
        if req_list is None:
            return None
        req_out: List[str] = []
        for x in req_list:
            if not isinstance(x, str):
                return None
            req_out.append(x)
        required_lists.append(req_out)

    if [_IMPORT_KEY] not in required_lists:
        return None
    core = [x for x in required_lists if x != [_IMPORT_KEY]]
    if len(core) != 1:
        return None
    return set(core[0])


def _enum_values(node: Mapping[str, Any]) -> List[str]:
    raw = node.get("enum")
    raw_list = _as_list(raw)
    if raw_list is None:
        return []
    out: List[str] = []
    for x in raw_list:
        if isinstance(x, str):
            out.append(x)
    return out


def _has_rich_doc(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return ("```" in stripped) or ("\n\n" in stripped) or ("\n- " in stripped)


def _count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _is_allof_ref_wrapper(node: Mapping[str, Any]) -> bool:
    all_of = node.get("allOf")
    all_of_list = _as_list(all_of)
    if all_of_list is None or len(all_of_list) != 1:
        return False
    if _as_dict(all_of_list[0]) is None:
        return False
    return _extract_ref_target(node) is not None


def _is_nullable_oneof(node: Mapping[str, Any]) -> bool:
    one_of_list = _as_list(node.get("oneOf"))
    if one_of_list is None or len(one_of_list) != _NULLABLE_UNION_OPTION_COUNT:
        return False
    options: List[Mapping[str, Any]] = []
    for item in one_of_list:
        item_dict = _as_dict(item)
        if item_dict is not None:
            options.append(item_dict)
    if len(options) != _NULLABLE_UNION_OPTION_COUNT:
        return False
    return any(_schema_types(opt) == ["null"] for opt in options)


def _infer_doc_level(*, node: Mapping[str, Any], base_md: str) -> str:  # noqa: PLR0911
    # `enum` 节点强制使用 `full` 模板
    if _has_enum(node):
        return "full"
    ref_wrapper = _is_allof_ref_wrapper(node) or _is_nullable_oneof(node)
    if _is_container_schema(node) or ref_wrapper:
        # 复杂容器节点(例如 `outputs.aggregate.fields`)需要 `full`;基础容器保持 `brief` 以减少悬停噪音.
        if "参数" in base_md:
            return "full"
        if _has_rich_doc(base_md) and _count_non_empty_lines(base_md) >= _DOC_LEVEL_FULL_MIN_NON_EMPTY_LINES:
            return "full"
        return "brief"
    if ("oneOf" in node) or ("anyOf" in node) or ("allOf" in node):
        return "full"
    if _has_rich_doc(base_md):
        return "full"
    return "brief"


def _build_constraints_summary(  # noqa: C901, PLR0912, PLR0915
    node: Mapping[str, Any],
    *,
    required: Optional[bool],
    parent_has_import_workaround: bool,
    referenced_schema: Optional[Mapping[str, Any]],
) -> List[str]:
    lines: List[str] = []

    if required is True:
        if parent_has_import_workaround:
            lines.append("- 必填: 是(除非仅提供 `{}`)".format(_IMPORT_KEY))
        else:
            lines.append("- 必填: 是")
    elif required is False:
        lines.append("- 必填: 否")

    effective = referenced_schema or node

    # 类型信息 / `oneOf` / 可空性
    types = _schema_types(effective)
    if types:
        lines.append("- 类型: {}".format(" | ".join(types)))
    elif "oneOf" in effective or "anyOf" in effective or "allOf" in effective:
        # 保持输出稳定且尽量紧凑
        for key in ("oneOf", "anyOf", "allOf"):
            if key in effective and isinstance(effective.get(key), list):
                lines.append("- {}".format(key))

    enum = _enum_values(effective)
    if enum:
        preview = ", ".join("`{}`".format(x) for x in enum)
        lines.append("- 取值: {}".format(preview))

    if "const" in effective:
        lines.append("- const: `{}`".format(effective.get("const")))

    if "default" in effective:
        lines.append("- 默认值: `{}`".format(effective.get("default")))

    for key in ("minLength", "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
        if key in effective:
            lines.append("- {}: `{}`".format(key, effective.get(key)))

    for key in ("minItems", "maxItems", "uniqueItems"):
        if key in effective:
            lines.append("- {}: `{}`".format(key, effective.get(key)))

    items = _as_dict(effective.get("items"))
    if items is not None:
        item_types = _schema_types(items)
        if item_types:
            lines.append("- items: {}".format(" | ".join(item_types)))
        if isinstance(items.get("enum"), list):
            values = _enum_values(items)
            if values:
                preview = ", ".join("`{}`".format(x) for x in values)
                lines.append("- items.取值: {}".format(preview))
    else:
        items_list = _as_list(effective.get("items"))
        if items_list:
            lines.append("- items: tuple(len={})".format(len(items_list)))

    for key in ("minProperties", "maxProperties"):
        if key in effective:
            lines.append("- {}: `{}`".format(key, effective.get(key)))

    if "additionalProperties" in effective:
        ap = effective.get("additionalProperties")
        if ap is False:
            lines.append("- additionalProperties: false")
        elif ap is True:
            lines.append("- additionalProperties: true")
        elif isinstance(ap, dict):
            ap_types = _schema_types(cast("Mapping[str, Any]", ap))
            if ap_types:
                lines.append("- additionalProperties: {}".format(" | ".join(ap_types)))
            else:
                lines.append("- additionalProperties: object")

    if "propertyNames" in effective:
        lines.append("- propertyNames: configured")

    # `$import` 兜底规则汇总: 仅对对象层级的 `schema`(通常是 `definition`)有意义
    workaround_required = _detect_import_required_workaround(effective)
    if workaround_required is not None:
        core = sorted(workaround_required)
        if core:
            lines.append("- required: `{}` 或 仅 `{}`".format("`, `".join(core), _IMPORT_KEY))
        else:
            lines.append("- required: 仅 `{}`".format(_IMPORT_KEY))

    if not lines:
        # 保持输出稳定;不要生成空段落
        return ["- (无)"]

    return lines


def _render_examples_section(
    node: Mapping[str, Any],
    *,
    effective_schema: Optional[Mapping[str, Any]],
    config_path: str,
    snippet_index: Mapping[str, str],
    fallback_note: str,
) -> List[str]:
    schema = effective_schema or node
    examples_list = _as_list(schema.get("examples"))
    if examples_list:
        rendered: List[str] = []
        for example in examples_list:
            rendered.append("```yaml")
            rendered.extend(_yaml_dump(example).rstrip("\n").splitlines())
            rendered.append("```")
        return rendered

    snippet = _lookup_snippet(snippet_index, config_path=config_path)
    if isinstance(snippet, str) and snippet.strip():
        rendered = ["```yaml"]
        rendered.extend(snippet.rstrip("\n").splitlines())
        rendered.append("```")
        return rendered

    # 兜底: 生成最小且 `schema-only` 合法的值
    rendered = [fallback_note, "```yaml"]
    rendered.extend(_yaml_dump(_build_minimal_schema_valid_value(schema)).rstrip("\n").splitlines())
    rendered.append("```")
    return rendered


def _lookup_snippet(snippet_index: Mapping[str, str], *, config_path: str, max_ancestors: int = 4) -> Optional[str]:
    """根据配置路径查找示例片段.

    优先级:
    1) 精确匹配 `config_path`
    2) 逐层向上回退到祖先路径(最多 `max_ancestors` 层),用于复用更大粒度的片段.
    """

    current = str(config_path or "")
    for _ in range(max(1, int(max_ancestors))):
        if current in snippet_index:
            return snippet_index.get(current)
        if "." not in current:
            break
        current = current.rsplit(".", 1)[0]
    return None


def _build_minimal_schema_valid_value(node: Mapping[str, Any]) -> Any:  # noqa: C901, PLR0911, PLR0912, PLR0915
    # 优先使用 `const` / `default` / `enum`
    if "const" in node:
        return node.get("const")
    if "default" in node:
        return node.get("default")
    enum = _enum_values(node)
    if enum:
        return enum[0]

    # 处理可空的联合类型
    for key in ("oneOf", "anyOf"):
        raw_list = _as_list(node.get(key))
        if raw_list:
            # 尽量选择非 `null` 的分支
            options: List[Mapping[str, Any]] = []
            for x in raw_list:
                x_dict = _as_dict(x)
                if x_dict is not None:
                    options.append(x_dict)
            if not options:
                continue
            non_null: List[Mapping[str, Any]] = []
            for opt in options:
                types = _schema_types(opt)
                if types == ["null"] or (len(types) == 1 and types[0] == "null"):
                    continue
                non_null.append(opt)

            candidates = non_null or options

            # NOTE: 这类联合常见于“约束表达”(例如 `anyOf: [{required: [...]}, {required: ["$import"]}]`);
            # 这种分支本身不携带值形状信息,直接递归会导致返回 `null` 并生成无效示例.
            value_schemas: List[Mapping[str, Any]] = []
            for opt in candidates:
                if _schema_types(opt):
                    value_schemas.append(opt)
                    continue
                if _is_container_schema(opt):
                    value_schemas.append(opt)
                    continue
                if "$ref" in opt:
                    value_schemas.append(opt)
                    continue
                for hint_key in ("const", "default", "enum"):
                    if hint_key in opt:
                        value_schemas.append(opt)
                        break

            if value_schemas:
                return _build_minimal_schema_valid_value(value_schemas[0])

    types = _schema_types(node)
    if "null" in types and len(types) == 1:
        return None
    if "string" in types:
        min_len = node.get("minLength")
        if isinstance(min_len, int) and min_len > 0:
            return "x" * min_len
        return "demo"
    if "integer" in types:
        minimum = node.get("minimum")
        if isinstance(minimum, int):
            return minimum
        return 0
    if "number" in types:
        minimum = node.get("minimum")
        if isinstance(minimum, (int, float)):
            return minimum
        return 0.0
    if "boolean" in types:
        return True
    if "array" in types or "items" in node:
        min_items = node.get("minItems")
        item_schema = _as_dict(node.get("items"))
        item_value = _build_minimal_schema_valid_value(item_schema) if item_schema is not None else None
        if isinstance(min_items, int) and min_items > 0:
            return [item_value for _ in range(min_items)]
        return []
    if "object" in types or "properties" in node:
        workaround_required = _detect_import_required_workaround(node)
        props = _as_dict(node.get("properties"))
        if workaround_required is not None and props is not None and (_IMPORT_KEY in props):
            return {_IMPORT_KEY: "common.demo"}

        required = _as_str_list(node.get("required"))
        if workaround_required is not None and not required:
            # NOTE: `required` 被 `anyOf` 兜底规则隐藏,但 `$import` 仍可单独通过校验.
            return {_IMPORT_KEY: "common.demo"}

        if props is not None and required:
            out: Dict[str, Any] = {}
            for key in required:
                child = props.get(key)
                child_dict = _as_dict(child)
                out[key] = _build_minimal_schema_valid_value(child_dict) if child_dict is not None else None
            return out
        return {}

    # 未知类型: 返回 `null`(即 `None`)
    return None


def _ensure_enum_semantics_markdown(  # noqa: C901
    base_md: str, enum_values: Sequence[str], *, node_path: str
) -> None:
    """确保 `enum` 的“取值语义”在说明部分被逐项列出.

    约束(保守但可执行):
    - 每个枚举值必须至少出现于一条列表项行(`- ...`)中
    - 该行只能描述该单个枚举值(不得在同一行出现多个枚举值)
    - 该行必须包含除枚举值本身以外的解释文本
    """

    values = [x for x in enum_values if x]
    if not values:
        return

    found: Dict[str, str] = {}
    for raw in base_md.splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        present = [v for v in values if ("`{}`".format(v) in line)]
        if len(present) != 1:
            continue
        val = present[0]
        if val not in found:
            found[val] = line

    missing: List[str] = []
    weak: List[str] = []
    for val in values:
        line = found.get(val)
        if not line:
            missing.append(val)
            continue
        stripped = line.replace("`{}`".format(val), "").strip()
        # "- `x`" / "- `x`:" / "- `x`:" 都认为缺少行为解释(仅列值不足以作为语义)
        stripped = stripped.lstrip("-").strip()
        if stripped in ("", ":", "\uff1a"):
            weak.append(val)

    if missing or weak:
        parts: List[str] = []
        if missing:
            parts.append("missing={}".format(",".join(missing)))
        if weak:
            parts.append("weak={}".format(",".join(weak)))
        msg = "Enum docs invalid at {} ({}): enum={}".format(node_path, " ".join(parts), ",".join(values))
        raise ValueError(msg)


def standardize_schema_docs(  # noqa: C901, PLR0915
    schema: Dict[str, Any],
    *,
    fixture_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """生成/改写所有可达配置项节点的 `description` / `markdownDescription`(仅生成期使用)."""

    # 构建一次片段索引(仅生成期使用). 键=`config_path`, 值=片段文本.
    snippet_index = _build_snippet_index(fixture_paths or ())

    definitions_raw = schema.get("definitions")
    typed_definitions: Dict[str, Any] = cast("Dict[str, Any]", definitions_raw) if isinstance(definitions_raw, dict) else {}
    definition_roots = _infer_definition_roots(schema, definitions=typed_definitions)

    def resolve_ref(def_name: Optional[str]) -> Optional[Mapping[str, Any]]:
        if not def_name:
            return None
        target = typed_definitions.get(def_name)
        return cast("Mapping[str, Any]", target) if isinstance(target, dict) else None

    def walk_node(node: Any, *, path: str, required: Optional[bool], parent_import_workaround: bool, in_constraint: bool) -> None:
        walk_node_impl(
            node,
            path=path,
            required=required,
            parent_import_workaround=parent_import_workaround,
            in_constraint=in_constraint,
            document_self=True,
        )

    def walk_node_impl(  # noqa: C901, PLR0912, PLR0915
        node: Any,
        *,
        path: str,
        required: Optional[bool],
        parent_import_workaround: bool,
        in_constraint: bool,
        document_self: bool,
    ) -> None:
        if not isinstance(node, dict):
            return
        typed = cast("Dict[str, Any]", node)

        if document_self and (not in_constraint):
            base_md = ""
            if isinstance(typed.get("markdownDescription"), str):
                base_md = cast("str", typed["markdownDescription"])
            elif isinstance(typed.get("description"), str):
                base_md = cast("str", typed["description"])

            # 若存在引用的 `schema`,优先在引用对象上判断 `$import` 兜底规则
            referenced_schema = resolve_ref(_extract_ref_target(typed))
            workaround_required = _detect_import_required_workaround(referenced_schema or typed)
            has_import_workaround = workaround_required is not None

            doc_level = _infer_doc_level(node=typed, base_md=base_md)

            if doc_level == "brief":
                summary = _first_non_empty_lines(base_md or path, max_lines=3)
                if has_import_workaround and ("$import" not in summary):
                    # `brief` 模板仍需表达 `$import` 的“二选一”语义,避免误导用户认为必填字段永远必填.
                    import_line = "- 或仅 `{}`(展开后再校验必填字段)".format(_IMPORT_KEY)
                    lines = [ln for ln in summary.splitlines() if ln.strip()]
                    if lines:
                        if len(lines) >= _DOC_LEVEL_BRIEF_IMPORT_MAX_LINES:
                            lines[-1] = import_line
                        else:
                            lines.append(import_line)
                        summary = "\n".join(lines)
                typed["description"] = _first_non_empty_line(summary) or path
                typed["markdownDescription"] = "#### {}\n\n{}".format(path, summary or path)
            else:
                enum_values = _enum_values(typed)
                if enum_values:
                    _ensure_enum_semantics_markdown(base_md, enum_values, node_path=path)

                constraints = _build_constraints_summary(
                    typed,
                    required=required,
                    parent_has_import_workaround=parent_import_workaround,
                    referenced_schema=referenced_schema,
                )
                examples = _render_examples_section(
                    typed,
                    effective_schema=referenced_schema,
                    config_path=path,
                    snippet_index=snippet_index,
                    fallback_note=fallback_note,
                )
                description = _first_non_empty_line(base_md) or path
                typed["description"] = description
                typed["markdownDescription"] = "\n".join(
                    [
                        "#### {}".format(path),
                        "",
                        (base_md.strip() or description),
                        "",
                        "##### 字段约束",
                        "\n".join(constraints),
                        "",
                        "##### 例子",
                        "\n".join(examples),
                    ]
                ).rstrip()

        # 递归到结构性子节点
        next_import_workaround = parent_import_workaround
        if not in_constraint:
            workaround_required = _detect_import_required_workaround(typed)
            next_import_workaround = workaround_required is not None

            required_set: Set[str] = set(_as_str_list(typed.get("required")))
            if not required_set and workaround_required is not None:
                required_set = set(workaround_required)

            props = typed.get("properties")
            if isinstance(props, dict):
                for key, child in cast("Dict[str, Any]", props).items():
                    if not isinstance(child, dict):
                        continue
                    child_path = "{}.{}".format(path, key) if path else key
                    child_required = key in required_set if required_set else False
                    walk_node_impl(
                        child,
                        path=child_path,
                        required=child_required,
                        parent_import_workaround=next_import_workaround,
                        in_constraint=False,
                        document_self=True,
                    )

        # 数组元素 `items`
        items = typed.get("items")
        if isinstance(items, dict):
            walk_node_impl(
                items,
                path="{}[*]".format(path),
                required=None,
                parent_import_workaround=next_import_workaround,
                in_constraint=in_constraint,
                document_self=False,
            )
        else:
            items_list = _as_list(items)
            if items_list is not None:
                for item in items_list:
                    walk_node_impl(
                        item,
                        path="{}[*]".format(path),
                        required=None,
                        parent_import_workaround=next_import_workaround,
                        in_constraint=in_constraint,
                        document_self=False,
                    )

        # 映射的值节点: `additionalProperties`
        ap = typed.get("additionalProperties")
        if isinstance(ap, dict):
            walk_node_impl(
                ap,
                path="{}.*".format(path),
                required=None,
                parent_import_workaround=next_import_workaround,
                in_constraint=in_constraint,
                document_self=False,
            )

        # 联合类型: `oneOf` / `anyOf` / `allOf`
        for key, next_in_constraint in (("oneOf", in_constraint), ("anyOf", True), ("allOf", True)):
            raw_list = _as_list(typed.get(key))
            if raw_list is not None:
                for opt in raw_list:
                    walk_node_impl(
                        opt,
                        path=path,
                        required=required,
                        parent_import_workaround=next_import_workaround,
                        in_constraint=next_in_constraint,
                        document_self=False,
                    )

        # 嵌套的 `definitions` (少见)
        defs = typed.get("definitions")
        if isinstance(defs, dict) and not in_constraint:
            for name, def_schema in cast("Dict[str, Any]", defs).items():
                if not isinstance(def_schema, dict):
                    continue
                walk_node_impl(
                    def_schema,
                    path=name,
                    required=None,
                    parent_import_workaround=False,
                    in_constraint=False,
                    document_self=False,
                )

    fallback_note = "(兜底最小示例; 仅保证 schema-only 合法)"

    # 根节点 `properties`
    root_props = schema.get("properties")
    if isinstance(root_props, dict):
        for key, value in cast("Dict[str, Any]", root_props).items():
            if not isinstance(value, dict):
                continue
            walk_node(
                value, path=key, required=key in _as_str_list(schema.get("required")), parent_import_workaround=False, in_constraint=False
            )

    # `definitions` 子树(作为独立根节点遍历)
    for def_name, def_schema in typed_definitions.items():
        if not isinstance(def_schema, dict):
            continue
        def_path = definition_roots.get(def_name, def_name)
        walk_node_impl(def_schema, path=def_path, required=None, parent_import_workaround=False, in_constraint=False, document_self=False)

    return schema


def _infer_definition_roots(schema: Mapping[str, Any], *, definitions: Mapping[str, Any]) -> Dict[str, str]:
    """根据 `$ref` 的引用路径推导每个 `definition` 的规范根路径.

    注意:
    - `definitions` 可能被多处引用;我们用“最长公共后缀”生成更稳定/更不误导的路径根.
    - 若找不到引用,回退为 `definition` 名称本身.
    """

    if not definitions:
        return {}

    paths_by_def = _collect_definition_reference_paths(schema, definitions=definitions)
    roots: Dict[str, str] = {}
    for def_name in definitions:
        paths = sorted(paths_by_def.get(def_name) or [])
        if not paths:
            roots[def_name] = str(def_name)
            continue
        if len(paths) == 1:
            roots[def_name] = str(paths[0])
            continue
        roots[def_name] = _longest_common_suffix_path(paths)
    return roots


def _collect_definition_reference_paths(  # noqa: C901
    schema: Mapping[str, Any], *, definitions: Mapping[str, Any]
) -> Dict[str, Set[str]]:
    """收集从 `schema` 可达结构中对 `definitions` 的引用路径.

    实现:
    - 从根 `schema` 扫描并递归进入已发现的 `definition`,单次扫描 O(N)
    - 支持嵌套 `$ref`(`definition` 内部引用 `definition`)
    - 仅收集结构性引用(跳过 `allOf/anyOf` 约束上下文内的 `properties`).
    """

    found: Dict[str, Set[str]] = {}
    visited: Set[Tuple[str, str]] = set()

    def enqueue(def_name: str, *, at_path: str) -> None:
        found.setdefault(def_name, set()).add(at_path)
        key = (def_name, at_path)
        if key in visited:
            return
        visited.add(key)
        target = definitions.get(def_name)
        if isinstance(target, dict):
            walk(cast("Mapping[str, Any]", target), path=at_path, in_constraint=False)

    def walk(node: Any, *, path: str, in_constraint: bool) -> None:  # noqa: C901, PLR0912
        if not isinstance(node, dict):
            return
        typed = cast("Mapping[str, Any]", node)

        ref = _extract_ref_target(typed)
        if ref is not None:
            enqueue(str(ref), at_path=path)
            # NOTE: `$ref` 节点本身不直接展开;由 `enqueue()` 驱动展开,避免在原树上重复遍历同一对象.

        # 递归 `properties`
        if not in_constraint:
            props = typed.get("properties")
            if isinstance(props, dict):
                for key, child in cast("Dict[str, Any]", props).items():
                    if not isinstance(child, dict):
                        continue
                    child_path = "{}.{}".format(path, key) if path else str(key)
                    walk(child, path=child_path, in_constraint=False)

        # 数组 `items`
        items = typed.get("items")
        if isinstance(items, dict):
            walk(items, path="{}[*]".format(path), in_constraint=in_constraint)
        else:
            items_list = _as_list(items)
            if items_list is not None:
                for item in items_list:
                    walk(item, path="{}[*]".format(path), in_constraint=in_constraint)

        # 映射的值节点: `additionalProperties`
        ap = typed.get("additionalProperties")
        if isinstance(ap, dict):
            walk(ap, path="{}.*".format(path), in_constraint=in_constraint)

        # 联合类型/约束: `oneOf` / `anyOf` / `allOf`
        for key, child_constraint in (("oneOf", in_constraint), ("anyOf", True), ("allOf", True)):
            raw_list = _as_list(typed.get(key))
            if raw_list is not None:
                for opt in raw_list:
                    walk(opt, path=path, in_constraint=child_constraint)

    walk(schema, path="", in_constraint=False)
    return found


def _longest_common_suffix_path(paths: Sequence[str]) -> str:
    segs: List[List[str]] = [p.split(".") if p else [] for p in paths]
    if not segs:
        return ""
    rev = [list(reversed(s)) for s in segs]
    out_rev: List[str] = []
    for idx in range(min(len(s) for s in rev)):
        token = rev[0][idx]
        if all(s[idx] == token for s in rev[1:]):
            out_rev.append(token)
        else:
            break
    return ".".join(reversed(out_rev))


def _build_snippet_index(fixture_paths: Sequence[str]) -> Dict[str, str]:
    """从一组样例文件构建片段索引.

    索引结构:
    - 键: 片段 `id`
    - 值: 片段内容(不含 `BEGIN`/`END` 标记行)
    """

    if not fixture_paths:
        return {}

    cache_key = tuple(str(p) for p in fixture_paths)
    cached = _SNIPPET_INDEX_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    index: Dict[str, str] = {}
    for path in fixture_paths:
        file_index = _extract_snippets_from_fixture(path)
        for snippet_id, snippet_text in file_index.items():
            if snippet_id not in index:
                index[snippet_id] = snippet_text
    _SNIPPET_INDEX_CACHE[cache_key] = dict(index)
    return index


def _extract_snippets_from_fixture(path: str) -> Dict[str, str]:  # noqa: C901
    # 单次扫描 O(N) 的提取器,支持嵌套
    with Path(path).open("r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    stack: List[str] = []
    buffers: Dict[str, List[str]] = {}
    for line in lines:
        begin = _BEGIN_SNIPPET_RE.match(line)
        if begin:
            snippet_id = begin.group("id")
            stack.append(snippet_id)
            if snippet_id not in buffers:
                buffers[snippet_id] = []
            continue
        end = _END_SNIPPET_RE.match(line)
        if end:
            snippet_id = end.group("id")
            if not stack or stack[-1] != snippet_id:
                msg = "Invalid snippet nesting in {}: END {} does not match stack {}".format(
                    path, snippet_id, stack[-1] if stack else "<empty>"
                )
                raise ValueError(msg)
            _ = stack.pop()
            continue

        if not stack:
            continue
        for active in stack:
            buffers[active].append(line)

    if stack:
        msg = "Invalid snippet nesting in {}: unterminated BEGIN {}".format(path, ", ".join(stack))
        raise ValueError(msg)

    out: Dict[str, str] = {}
    for snippet_id, buf in buffers.items():
        content = "\n".join(buf).rstrip() + "\n"
        if content.strip():
            out[snippet_id] = content
    return out


_SNIPPET_INDEX_CACHE: Dict[Tuple[str, ...], Dict[str, str]] = {}


__all__ = ("standardize_schema_docs",)
