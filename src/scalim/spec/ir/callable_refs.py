from typing import Tuple, Union

from ...vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class PythonReferenceIr:
    """`Python` 可调用引用描述(纯数据,不执行 `import`/解析).

    说明:
    - `module_path` 可以是绝对路径(例如 `pkg.mod`)或相对路径(例如 `.pkg.mod`).
    - `style` 仅用于调试/诊断(例如 `dotted`/`class`).
    """

    reference: str
    module_path: str
    attr_path: Tuple[str, ...]
    style: str


@dataclass(frozen=True)
class BuiltinCallableIdIr:
    """内置可调用对象标识符描述.

    说明:
    - 该描述本身不会解析为 `Python` 函数对象.
    - “运行时链接”阶段负责根据内置词表/注册表将其解析为具体实现.
    """

    callable_id: str


@dataclass(frozen=True)
class RuntimeHandleIdIr:
    """运行时句柄标识符描述(通过 `RuntimeBindings` 注册表解析,不执行 `import`).

    说明:
    - 主要用于 `Python` DSL/代码侧构造 `IR`: 当函数对象无法/不适合表示为可导入引用时,使用句柄标识符在运行时绑定阶段注入.
    """

    handle_id: str


CallableRefIr = Union[PythonReferenceIr, BuiltinCallableIdIr, RuntimeHandleIdIr]


def describe_callable_ref(ref: CallableRefIr) -> str:
    """尽力提供稳定的字符串描述,用于诊断与快照."""

    if isinstance(ref, PythonReferenceIr):
        return str(ref.reference)
    if isinstance(ref, BuiltinCallableIdIr):
        return "^{}".format(ref.callable_id)
    return "runtime:{}".format(ref.handle_id)


__all__ = (
    "BuiltinCallableIdIr",
    "CallableRefIr",
    "PythonReferenceIr",
    "RuntimeHandleIdIr",
    "describe_callable_ref",
)
