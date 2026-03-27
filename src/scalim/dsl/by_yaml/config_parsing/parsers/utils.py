from typing import Any, Dict, List, Optional, cast


def str_or_none(v: Any) -> Optional[str]:
    return str(v) if v is not None else None


def mapping_or_none(value: object) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    return cast("Dict[str, Any]", value)  # pragma: allow-cast yaml mapping typed narrowing


def list_or_none(value: object) -> Optional[List[Any]]:
    if not isinstance(value, list):
        return None
    return cast("List[Any]", value)  # pragma: allow-cast yaml list typed narrowing
