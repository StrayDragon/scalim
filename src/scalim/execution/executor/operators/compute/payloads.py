from typing import Any, Dict, Tuple


def build_field_compute_dependencies_payload(dep_keys: Tuple[str, ...], dep_values: Tuple[Any, ...]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    i = 0
    while i < len(dep_keys):
        payload[dep_keys[i]] = dep_values[i]
        i += 1
    return payload


__all__ = ("build_field_compute_dependencies_payload",)
