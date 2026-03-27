"""钩子接口与实现.

对外推荐优先从包根导入(避免绑定到内部模块文件名),例如:
- `from scalim.hooks import HookManager, BaseHook`
"""

from ._base import BaseHook, Hook, HookManager, IExecutionHook
from ._dispatch import HookDispatchStrategy
from ._internal.common import HOOK_RAISED_EXCEPTION_WARNING

__all__ = (
    "HOOK_RAISED_EXCEPTION_WARNING",
    "BaseHook",
    "Hook",
    "HookDispatchStrategy",
    "HookManager",
    "IExecutionHook",
)
