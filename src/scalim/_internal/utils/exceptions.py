"""异常处理相关的内部小工具(非稳定入口).

注意:
- 该模块属于跨领域基础设施,用于 `execution`/`workflow` 等多个领域复用.
- 依赖方向必须保持向下: 该模块不得依赖上层领域模块,避免层级反转与循环导入.
"""

import copy
from contextlib import suppress


def clone_exception_for_reraise(exc: BaseException) -> BaseException:
    """尽力而为地克隆异常对象,用于跨线程/跨状态传播后重新抛出.

    策略:
    - 优先 `copy.copy(exc)` (保留异常类型/属性,但可能失败)
    - 失败后尝试 `exc.__class__(*exc.args)` (降维为 `type + args`)
    - 再失败则回退到原异常对象

    并尽量 `with_traceback(None)` 清理 `traceback`,避免将 `owner` 线程栈引用长期保存在共享状态中.
    """

    try:
        cloned = copy.copy(exc)
    except Exception:  # noqa: BLE001
        cloned = None
    if isinstance(cloned, BaseException):
        with suppress(Exception):
            cloned = cloned.with_traceback(None)
        return cloned

    try:
        cloned = exc.__class__(*exc.args)
    except Exception:  # noqa: BLE001
        cloned = exc

    with suppress(Exception):
        cloned = cloned.with_traceback(None)
    return cloned


__all__ = ()
