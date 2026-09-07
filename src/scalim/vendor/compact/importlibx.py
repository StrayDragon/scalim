# region imports

import importlib
from collections.abc import Callable
from types import ModuleType

# endregion


ImportModuleFn = Callable[[str], ModuleType]

# 测试用的显式替换点:请补丁 `IMPORT_MODULE`,而不要去补丁 `builtins.__import__` / `importlib.import_module`.
IMPORT_MODULE: ImportModuleFn = importlib.import_module


def import_module(module_name: str) -> ModuleType:
    return IMPORT_MODULE(module_name)


def require_optional_dependency(
    module_name: str,
    *,
    context: str | None = None,
    install_name: str | None = None,
) -> ModuleType:
    """导入可选依赖;若不可用则抛出统一的错误信息."""
    try:
        return import_module(module_name)
    except ImportError as exc:
        owner = context or "scalim"
        pkg = install_name or module_name
        if install_name is not None and install_name != module_name:
            msg = f"{owner} 需要安装 {pkg} 库(导入名: {module_name}).\n请安装: pip install {pkg}\n或者: uv add {pkg}"
        else:
            msg = f"{owner} 需要安装 {pkg} 库.\n请安装: pip install {pkg}\n或者: uv add {pkg}"
        raise ImportError(msg) from exc


__all__ = (
    "IMPORT_MODULE",
    "ImportModuleFn",
    "import_module",
    "require_optional_dependency",
)
