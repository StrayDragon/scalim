from typing import Any, Dict, List, Optional, Sequence, cast

from ...vendor.compact.typing_extensionsx import TypedDict
from .runtime.introspection import load_output_config as _load_output_config
from .runtime.references import derive_base_module_path as _derive_base_module_path


class OutputConfigDict(TypedDict):
    params: Dict[str, Any]
    field_name_mapping: Dict[str, str]
    output_fields: List[str]
    outputs: List[Dict[str, Any]]


def load_output_config(yaml_path: str) -> OutputConfigDict:
    return cast("OutputConfigDict", cast("object", _load_output_config(yaml_path)))


def derive_base_module_path(
    yaml_path: str,
    *,
    sys_path: Optional[Sequence[Optional[str]]] = None,
    cwd: Optional[str] = None,
) -> str:
    return _derive_base_module_path(yaml_path, sys_path=sys_path, cwd=cwd)


__all__ = [
    "OutputConfigDict",
    "derive_base_module_path",
    "load_output_config",
]
