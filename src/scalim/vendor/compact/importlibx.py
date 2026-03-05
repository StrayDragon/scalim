# region imports

import importlib
from types import ModuleType
from typing import Callable, Optional

# endregion


ImportModuleFn = Callable[[str], ModuleType]

# 测试用的显式替换点:请补丁 `IMPORT_MODULE`,而不要去补丁 `builtins.__import__` / `importlib.import_module`.
IMPORT_MODULE: ImportModuleFn = importlib.import_module


def import_module(module_name: str) -> ModuleType:
    return IMPORT_MODULE(module_name)


def require_optional_dependency(
    module_name: str,
    *,
    context: Optional[str] = None,
    install_name: Optional[str] = None,
) -> ModuleType:
    """导入可选依赖;若不可用则抛出统一的错误信息."""
    try:
        return import_module(module_name)
    except ImportError as exc:
        owner = context or "scalim"
        pkg = install_name or module_name
        if install_name is not None and install_name != module_name:
            msg = "{} 需要安装 {} 库(导入名: {}).\n请安装: pip install {}\n或者: uv add {}".format(
                owner,
                pkg,
                module_name,
                pkg,
                pkg,
            )
        else:
            msg = "{} 需要安装 {} 库.\n请安装: pip install {}\n或者: uv add {}".format(
                owner,
                pkg,
                pkg,
                pkg,
            )
        raise ImportError(msg) from exc


__all__ = [
    "IMPORT_MODULE",
    "ImportModuleFn",
    "import_module",
    "require_optional_dependency",
]
