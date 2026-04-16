"""策略决策 `signal` 的 `payload` 契约.

说明:
- 这些 `payload` 不是“可观测性事件”;它们是可变的 `decision` 对象,允许 `hook` 在运行期边界(例如 `pre-run_ir`)改写候选值.
- 运行时需兼容 `Python 3.6`.
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Sequence

from ..events import EventType
from ..vendor.dataclassesx import dataclass
from ..vendor.dataclassesx import field as dataclass_field
from ._base import HookManager

if TYPE_CHECKING:
    from ._internal.manager_base import ExecutionHookLike


@dataclass(frozen=True)
class DecisionOverrideHistoryEntry:
    hook_id: str
    prev_value: Optional[int]
    next_value: Optional[int]
    reason: str


@dataclass
class PreUseBatchSizeDecision:
    """`pre_use_batch_size` 的决策 `payload`.

    `hook` 处理器可调用 `override(...)` 改写 `value` 并追加 `history`.

    字段:
    - `value`: 当前候选 `batch_size`(`int >= 1`)或 `None`(不分批).
    - `history`: 改写审计轨迹(`hook_id` + `reason` + 值变更).
    - `run_id`/`demand_path`/`init_vars`: 可选上下文(供策略 `hook` 按不同需求画像自适应).
    - `main_loader`: 可选: 主数据源加载函数(若可获取).
    """

    value: Optional[int]
    run_id: Optional[str] = None
    demand_path: Optional[str] = None
    init_vars: Optional[Dict[str, object]] = None
    main_loader: Optional[object] = None
    history: List[DecisionOverrideHistoryEntry] = dataclass_field(default_factory=list)

    _active_hook_id: Optional[str] = dataclass_field(default=None, repr=False, compare=False)

    def _enter_hook(self, hook: object) -> None:
        self._active_hook_id = type(hook).__name__

    def _exit_hook(self) -> None:
        self._active_hook_id = None

    def override(self, next_value: object, *, reason: str) -> None:
        """改写候选值并记录 `history`."""
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            msg = "override(reason=...) is required and cannot be empty"
            raise ValueError(msg)

        if next_value is None:
            normalized_value = None
        else:
            if isinstance(next_value, bool) or not isinstance(next_value, int):
                msg = "batch_size override must be an integer >= 1 or None"
                raise TypeError(msg)
            if int(next_value) < 1:
                msg = "batch_size override must be >= 1 when provided"
                raise ValueError(msg)
            normalized_value = int(next_value)

        hook_id = str(self._active_hook_id or "<unknown>")
        prev = self.value
        self.value = normalized_value
        self.history.append(
            DecisionOverrideHistoryEntry(
                hook_id=hook_id,
                prev_value=prev,
                next_value=normalized_value,
                reason=normalized_reason,
            )
        )


def emit_pre_use_batch_size_signal(hooks: Sequence["ExecutionHookLike"], decision: PreUseBatchSizeDecision) -> None:
    """向钩子发射 `pre_use_batch_size` 策略决策 `signal`(类型化, 默认 `fail-fast`).

    说明:
    - 确定性顺序: 按钩子注册顺序分发.
    - `opt-in`: 仅实现 `on_pre_use_batch_size` 的钩子会收到.
    - 默认 `fail-fast`: 处理器异常直接向外抛出.
    """
    if not hooks:
        return

    manager = HookManager()
    for hook in hooks:
        manager.register(hook)
    manager.emit_typed_policy(EventType.PRE_USE_BATCH_SIZE, decision)


__all__ = (
    "DecisionOverrideHistoryEntry",
    "PreUseBatchSizeDecision",
    "emit_pre_use_batch_size_signal",
)
