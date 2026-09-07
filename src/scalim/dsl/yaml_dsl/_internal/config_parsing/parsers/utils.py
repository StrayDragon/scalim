from typing import Any

from ......_internal.type_narrowing import as_list, as_mapping


def str_or_none(v: Any) -> str | None:
    return str(v) if v is not None else None


def mapping_or_none(value: Any) -> dict[str, Any] | None:
    return as_mapping(value, path="yaml.mapping")


def list_or_none(value: Any) -> list[Any] | None:
    return as_list(value, path="yaml.list")


__all__ = ()
