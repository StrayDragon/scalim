# pragma: allow-non-core-file 测试 seam/可选依赖守卫,原 vendor 路径在覆盖率测量边界外;Stage C 迁址后沿用
"""可选依赖守卫与显式导入 `seam`(第一方实现,非上游拷贝).

- `IMPORT_MODULE` / `import_module`: 为测试提供可替换的导入点(勿直接 `patch` 内建导入).
- `require_optional_dependency`: 统一的可选依赖缺失报错口径.

保留策略: 第一方代码,长期保留;原 `vendor/compact/importlibx`(0.20.x `Stage C` 前路径),
迁移说明见仓库 `ROADMAP.md` 与 `AGENTS.md`.
"""

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


__all__ = ()
