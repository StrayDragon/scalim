"""`hooks` 稳定导出面.

说明:
- 对外稳定导入路径仍为 `scalim.hooks`
- `scalim.hooks._internal` 属于实现细节(非公共契约)
"""

from ._base import BaseHook, Hook, HookManager, IExecutionHook
from ._dispatch import HookDispatchStrategy
from ._internal.common import HOOK_RAISED_EXCEPTION_WARNING
from .policy_signals import DecisionOverrideHistoryEntry, PreUseBatchSizeDecision

__all__ = (
    "HOOK_RAISED_EXCEPTION_WARNING",
    "BaseHook",
    "DecisionOverrideHistoryEntry",
    "Hook",
    "HookDispatchStrategy",
    "HookManager",
    "IExecutionHook",
    "PreUseBatchSizeDecision",
)
