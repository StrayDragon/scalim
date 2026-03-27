from typing import Optional, Sequence

from .runtime.introspection import OutputConfigDict
from .runtime.introspection import load_output_config as _load_output_config
from .runtime.references import derive_base_module_path as _derive_base_module_path


def load_output_config(yaml_path: str) -> OutputConfigDict:
    return _load_output_config(yaml_path)


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
