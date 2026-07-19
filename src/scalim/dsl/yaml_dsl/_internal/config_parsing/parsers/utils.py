from typing import Any, Dict, List, Optional

from ......_internal.type_narrowing import as_list, as_mapping


def str_or_none(v: Any) -> Optional[str]:
    return str(v) if v is not None else None


def mapping_or_none(value: Any) -> Optional[Dict[str, Any]]:
    return as_mapping(value, path="yaml.mapping")


def list_or_none(value: Any) -> Optional[List[Any]]:
    return as_list(value, path="yaml.list")


__all__ = ()
