from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, cast


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


def _select_child_schema(schema: Dict[str, Any], root_schema: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    variants = _iter_effective_schemas(schema, root_schema, seen=set())

    for variant in variants:
        props: Any = variant.get("properties")
        if isinstance(props, dict) and key in props and isinstance(props[key], dict):
            return cast("Dict[str, Any]", props[key])

    for variant in variants:
        additional: Any = variant.get("additionalProperties")
        if isinstance(additional, dict):
            return cast("Dict[str, Any]", additional)

    return None


def _collect_property_keys(schema: Dict[str, Any], root_schema: Dict[str, Any]) -> Optional[FrozenSet[str]]:
    variants = _iter_effective_schemas(schema, root_schema, seen=set())
    # 对于 `additionalProperties` 为 `schema` 的“动态映射”, `key` 空间由调用方自定义,
    # 不应在此处做 `unknown-fields` 提示(否则会把合法的 `source_id`/`field_id` 等映射键误报为 `unknown`).
    for variant in variants:
        additional = variant.get("additionalProperties")
        if isinstance(additional, dict):
            return None
    saw_props = False
    keys: Set[str] = set()

    for variant in variants:
        props = variant.get("properties")
        if isinstance(props, dict):
            saw_props = True
            keys.update(cast("Dict[str, Any]", props))

    if saw_props:
        return frozenset(keys)
    return None


def _get_schema_properties(schema: Dict[str, Any], path: Sequence[str]) -> Optional[FrozenSet[str]]:
    root_schema = schema
    current: Dict[str, Any] = schema
    for key in path:
        next_schema = _select_child_schema(current, root_schema, key)
        if next_schema is None:
            return None
        current = next_schema

    return _collect_property_keys(current, root_schema)


def find_unknown_fields(
    yaml_data: Any,
    schema: Dict[str, Any],
    *,
    path: Optional[List[str]] = None,
) -> List[UnknownFieldIssue]:
    current_path = path or []
    if not isinstance(yaml_data, dict):
        return []

    yaml_dict = cast("Dict[Any, Any]", yaml_data)
    known_props = _get_schema_properties(schema, current_path)
    unknown: List[UnknownFieldIssue] = []

    for key, value in yaml_dict.items():
        key_str = str(key)
        if key_str.startswith("_"):
            continue

        next_path = [*current_path, key_str]
        path_str = ".".join(next_path)

        if known_props is not None and key_str not in known_props:
            suggestions: Tuple[str, ...] = ()
            if known_props:
                suggestions = tuple(get_close_matches(key_str, sorted(known_props), n=3, cutoff=0.5))
            unknown.append(UnknownFieldIssue(path=path_str, field=key_str, suggestions=suggestions))

        unknown.extend(_collect_nested_unknowns(value, schema, next_path))

    return unknown


def _collect_nested_unknowns(value: Any, schema: Dict[str, Any], current_path: List[str]) -> List[UnknownFieldIssue]:
    if isinstance(value, dict):
        return find_unknown_fields(value, schema, path=current_path)
    if isinstance(value, list):
        nested: List[UnknownFieldIssue] = []
        for i, item in enumerate(cast("List[Any]", value)):
            if isinstance(item, dict):
                nested.extend(find_unknown_fields(item, schema, path=[*current_path, str(i)]))
        return nested
    return []


__all__ = [
    "UnknownFieldIssue",
    "find_unknown_fields",
]
