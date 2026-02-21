# region imports

import importlib
from collections.abc import Callable
from types import ModuleType

# endregion


ImportModuleFn = Callable[[str], ModuleType]

# Explicit seam for tests: patch `IMPORT_MODULE` instead of patching `builtins.__import__` / `importlib.import_module`.
IMPORT_MODULE: ImportModuleFn = importlib.import_module


def import_module(module_name: str) -> ModuleType:
    return IMPORT_MODULE(module_name)


def require_optional_dependency(module_name: str, *, context: str | None = None) -> ModuleType:
    """Import optional dependency or raise a consistent error."""
    try:
        return import_module(module_name)
    except ImportError as exc:
        owner = context or "scalim"
        msg = f"{owner} 需要安装 {module_name} 库.\n请安装: pip install {module_name}\n或者: uv add {module_name}"
        raise ImportError(msg) from exc


__all__ = [
    "IMPORT_MODULE",
    "ImportModuleFn",
    "import_module",
    "require_optional_dependency",
]
