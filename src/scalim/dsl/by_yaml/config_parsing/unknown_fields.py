from difflib import get_close_matches
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, cast

from ....vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class UnknownFieldIssue:
    path: str
    field: str
    suggestions: Tuple[str, ...] = ()

    @property
    def message(self) -> str:
        return "Unknown field '{}'".format(self.field)


def _unescape_json_pointer(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def _resolve_json_pointer(root: Dict[str, Any], pointer: str) -> Optional[Dict[str, Any]]:
    if not pointer.startswith("#/"):
        return None

    current: Any = root
    for raw_part in pointer[2:].split("/"):
        part = _unescape_json_pointer(raw_part)
        if not isinstance(current, dict):
            return None
        current_dict = cast("Dict[str, Any]", current)
        if part not in current_dict:
            return None
        current = current_dict[part]

    return cast("Dict[str, Any]", current) if isinstance(current, dict) else None


def _deref_schema(schema: Dict[str, Any], root_schema: Dict[str, Any]) -> Dict[str, Any]:
    current = schema
    max_depth = 32
    for _ in range(max_depth):
        ref = current.get("$ref")
        if not isinstance(ref, str):
            return current
        resolved = _resolve_json_pointer(root_schema, ref)
        if resolved is None:
            return current
        current = resolved
    return current


def _iter_effective_schemas(schema: Dict[str, Any], root_schema: Dict[str, Any], *, seen: Set[int]) -> List[Dict[str, Any]]:
    current = _deref_schema(schema, root_schema)
    schema_id = id(current)
    if schema_id in seen:
        return []
    seen.add(schema_id)

    schemas: List[Dict[str, Any]] = [current]

    all_of = current.get("allOf")
    if isinstance(all_of, list):
        for item in cast("List[Any]", all_of):
            if isinstance(item, dict):
                schemas.extend(_iter_effective_schemas(cast("Dict[str, Any]", item), root_schema, seen=seen))

    return schemas


def _value_schema_types(value: Any) -> FrozenSet[str]:
    types: Set[str] = set()
    if value is None:
        types.add("null")
    elif isinstance(value, bool):
        types.add("boolean")
    elif isinstance(value, int):
        # `JSON Schema`: `integer` 是 `number` 的子集
        types.update(["integer", "number"])
    elif isinstance(value, float):
        types.add("number")
    elif isinstance(value, str):
        types.add("string")
    elif isinstance(value, list):
        types.add("array")
    elif isinstance(value, dict):
        types.add("object")
    return frozenset(types)


def _schema_type_set(schema: Dict[str, Any]) -> Optional[FrozenSet[str]]:
    typ = schema.get("type")
    if isinstance(typ, str) and typ:
        return frozenset({typ})
    if isinstance(typ, list):
        normalized = [str(t) for t in cast("List[Any]", typ) if isinstance(t, str) and t]
        if normalized:
            return frozenset(normalized)
    return None


def _schema_accepts_value(schema: Dict[str, Any], value: Any) -> bool:
    expected = _schema_type_set(schema)
    if expected is None:
        return True
    actual = _value_schema_types(value)
    if not actual:
        return True
    return bool(expected & actual)


def _extract_variant_candidates(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_variants: Any = schema.get("oneOf")
    if not isinstance(raw_variants, list):
        raw_variants = schema.get("anyOf")
    if not isinstance(raw_variants, list):
        return []
    return [cast("Dict[str, Any]", item) for item in cast("List[Any]", raw_variants) if isinstance(item, dict)]


def _filter_variants_by_value_type(
    candidates: List[Dict[str, Any]],
    *,
    root_schema: Dict[str, Any],
    value: Any,
) -> List[Dict[str, Any]]:
    return [c for c in candidates if _schema_accepts_value(_deref_schema(c, root_schema), value)]


def _visible_object_keys(value: Dict[Any, Any]) -> Tuple[str, ...]:
    return tuple(str(k) for k in value if not str(k).startswith("_"))


def _select_best_object_variants(
    candidates: List[Dict[str, Any]],
    *,
    root_schema: Dict[str, Any],
    value: Dict[Any, Any],
) -> List[Dict[str, Any]]:
    value_keys = _visible_object_keys(value)
    if not value_keys:
        return candidates

    def _hits(branch: Dict[str, Any]) -> int:
        keys = _collect_declared_property_keys(branch, root_schema)
        return sum(1 for k in value_keys if k in keys)

    scored = [(branch, _hits(branch)) for branch in candidates]
    best = max(score for _, score in scored)
    return [branch for branch, score in scored if score == best]


def _maybe_select_variant_branches(schema: Dict[str, Any], root_schema: Dict[str, Any], value: Any) -> List[Dict[str, Any]]:
    """对 `oneOf`/`anyOf` 做 `best-effort` 分支选择.

    规则:
    - 当分支声明了 `type` 时,先按类型过滤.
    - 对 `object` 值,按命中 `properties` 的 `key` 数量选择最匹配分支.
    - 无法区分时回退到 `union`(返回全部候选分支).
    """
    candidates = _extract_variant_candidates(schema)
    if not candidates:
        return []

    filtered = _filter_variants_by_value_type(candidates, root_schema=root_schema, value=value) or candidates
    if len(filtered) <= 1:
        return filtered

    if not isinstance(value, dict):
        return filtered
    return _select_best_object_variants(filtered, root_schema=root_schema, value=cast("Dict[Any, Any]", value))


def _iter_relevant_schemas(schema: Dict[str, Any], root_schema: Dict[str, Any], value: Any) -> List[Dict[str, Any]]:
    variants = _iter_effective_schemas(schema, root_schema, seen=set())
    selected: List[Dict[str, Any]] = []
    seen_ids: Set[int] = set()

    def _add(s: Dict[str, Any]) -> None:
        sid = id(s)
        if sid in seen_ids:
            return
        seen_ids.add(sid)
        selected.append(s)

    for v in variants:
        _add(v)
        for branch in _maybe_select_variant_branches(v, root_schema, value):
            for eff in _iter_effective_schemas(branch, root_schema, seen=set()):
                _add(eff)

    return selected


def _collect_declared_property_keys(schema: Dict[str, Any], root_schema: Dict[str, Any]) -> FrozenSet[str]:
    keys: Set[str] = set()
    for variant in _iter_effective_schemas(schema, root_schema, seen=set()):
        props = variant.get("properties")
        if isinstance(props, dict):
            keys.update([str(k) for k in cast("Dict[str, Any]", props)])
    return frozenset(keys)


def _merge_schema_variants(schemas: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not schemas:
        return None
    if len(schemas) == 1:
        return schemas[0]
    return {"anyOf": schemas}


def _collect_object_property_schema_variants(relevant: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, List[Dict[str, Any]]]]:
    saw_props = False
    property_variants: Dict[str, List[Dict[str, Any]]] = {}
    for variant in relevant:
        props = variant.get("properties")
        if not isinstance(props, dict):
            continue
        saw_props = True
        for key, value in cast("Dict[str, Any]", props).items():
            if not isinstance(value, dict):
                continue
            property_variants.setdefault(str(key), []).append(cast("Dict[str, Any]", value))
    return saw_props, property_variants


def _collect_additional_properties_schemas(relevant: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    additional_schemas: List[Dict[str, Any]] = []
    for variant in relevant:
        additional = variant.get("additionalProperties")
        if isinstance(additional, dict):
            additional_schemas.append(cast("Dict[str, Any]", additional))
    return additional_schemas


def _build_properties_schema_map(property_variants: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    properties_schema_map: Dict[str, Dict[str, Any]] = {}
    for key, schemas in property_variants.items():
        merged = cast("Dict[str, Any]", _merge_schema_variants(schemas))
        properties_schema_map[key] = merged
    return properties_schema_map


def _collect_object_schema_info(
    yaml_dict: Dict[Any, Any],
    schema: Dict[str, Any],
    root_schema: Dict[str, Any],
) -> Tuple[Optional[FrozenSet[str]], Dict[str, Dict[str, Any]], Optional[Dict[str, Any]]]:
    """返回 (`known_keys`, `properties_schema_map`, `additional_schema`).

    - `known_keys=None` 表示跳过该节点的 `unknown-keys` 检查.
    - `additional_schema`(如存在)用于“动态映射”(即 `additionalProperties` 为 `schema` 的场景).
    """

    relevant = _iter_relevant_schemas(schema, root_schema, yaml_dict)

    # 对于 `additionalProperties` 为 `schema` 的“动态映射”, `key` 空间由调用方自定义,
    # 不应在此处做 `unknown-fields` 提示(否则会把合法的 `source_id`/`field_id` 等映射键误报为 `unknown`).
    additional_schemas = _collect_additional_properties_schemas(relevant)
    dynamic_mapping = bool(additional_schemas)
    saw_props, property_variants = _collect_object_property_schema_variants(relevant)

    known_keys: Optional[FrozenSet[str]]
    if dynamic_mapping:
        known_keys = None
    elif saw_props:
        known_keys = frozenset(property_variants.keys())
    else:
        known_keys = None

    properties_schema_map = _build_properties_schema_map(property_variants)
    additional_schema = _merge_schema_variants(additional_schemas)
    return known_keys, properties_schema_map, additional_schema


def _resolve_array_item_schema(schema: Dict[str, Any], root_schema: Dict[str, Any], index: int, value: Any) -> Optional[Dict[str, Any]]:
    relevant = _iter_relevant_schemas(schema, root_schema, value)
    items_schemas: List[Dict[str, Any]] = []

    for variant in relevant:
        items_raw: Any = variant.get("items")
        if isinstance(items_raw, dict):
            items_schemas.append(cast("Dict[str, Any]", items_raw))
            continue
        if isinstance(items_raw, list):
            items_list = cast("List[Any]", items_raw)
            if 0 <= index < len(items_list) and isinstance(items_list[index], dict):
                items_schemas.append(cast("Dict[str, Any]", items_list[index]))
                continue
            additional_items = variant.get("additionalItems")
            if isinstance(additional_items, dict):
                items_schemas.append(cast("Dict[str, Any]", additional_items))

    if not items_schemas:
        return None
    if len(items_schemas) == 1:
        return items_schemas[0]
    return {"anyOf": items_schemas}


def find_unknown_fields(
    yaml_data: Any,
    schema: Dict[str, Any],
    *,
    path: Optional[List[str]] = None,
) -> List[UnknownFieldIssue]:
    return _collect_unknown_fields_node(yaml_data, schema, root_schema=schema, path=path or [])


def _collect_unknown_fields_object(
    yaml_dict: Dict[Any, Any],
    schema: Dict[str, Any],
    *,
    root_schema: Dict[str, Any],
    path: List[str],
) -> List[UnknownFieldIssue]:
    known_keys, property_schemas, additional_schema = _collect_object_schema_info(yaml_dict, schema, root_schema)
    unknown: List[UnknownFieldIssue] = []

    for k, v in yaml_dict.items():
        key = str(k)
        if key.startswith("_"):
            continue
        child_path = [*path, key]
        path_str = ".".join(child_path)

        if known_keys is not None and key not in known_keys:
            suggestions: Tuple[str, ...] = ()
            if known_keys:
                suggestions = tuple(get_close_matches(key, sorted(known_keys), n=3, cutoff=0.5))
            unknown.append(UnknownFieldIssue(path=path_str, field=key, suggestions=suggestions))

        child_schema = property_schemas.get(key) or additional_schema
        if child_schema is None:
            continue
        unknown.extend(_collect_unknown_fields_node(v, child_schema, root_schema=root_schema, path=child_path))

    return unknown


def _collect_unknown_fields_array(
    items: List[Any],
    schema: Dict[str, Any],
    *,
    root_schema: Dict[str, Any],
    path: List[str],
) -> List[UnknownFieldIssue]:
    nested: List[UnknownFieldIssue] = []
    for idx, item in enumerate(items):
        child_schema = _resolve_array_item_schema(schema, root_schema, idx, items)
        if child_schema is None:
            continue
        nested.extend(_collect_unknown_fields_node(item, child_schema, root_schema=root_schema, path=[*path, str(idx)]))
    return nested


def _collect_unknown_fields_node(
    value: Any,
    schema: Dict[str, Any],
    *,
    root_schema: Dict[str, Any],
    path: List[str],
) -> List[UnknownFieldIssue]:
    if isinstance(value, dict):
        return _collect_unknown_fields_object(cast("Dict[Any, Any]", value), schema, root_schema=root_schema, path=path)
    if isinstance(value, list):
        return _collect_unknown_fields_array(cast("List[Any]", value), schema, root_schema=root_schema, path=path)
    return []


__all__ = [
    "UnknownFieldIssue",
    "find_unknown_fields",
]
