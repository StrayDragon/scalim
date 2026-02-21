from typing import Any


def build_field_compute_dependencies_payload(dep_keys: tuple[str, ...], dep_values: tuple[Any, ...]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    i = 0
    while i < len(dep_keys):
        payload[dep_keys[i]] = dep_values[i]
        i += 1
    return payload


__all__ = [
    "build_field_compute_dependencies_payload",
]
