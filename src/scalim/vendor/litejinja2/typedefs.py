# region imports

from typing import Any, Callable, Dict, List, Optional, Union

from ..compact.typing_extensionsx import Literal, TypedDict

# endregion

NodeType = Literal["text", "var", "control"]
""" 节点类型定义 """


class TemplateNode(TypedDict):
    """模板节点结构

    表示解析后的模板中的一个节点,可以是文本、变量或控制结构.
    """

    type: NodeType  # 节点类型:`text`、`var` 或 `control`
    content: str  # 节点内容


VariableValue = Union[str, int, float, bool, List[Any], Dict[str, Any], None]
""" 变量值类型: 定义模板变量可以拥有的所有可能类型 """


FilterFunc = Callable[..., Any]  # 过滤器函数的类型
""" 过滤器相关类型 """


class FilterDef(TypedDict):
    """过滤器定义"""

    func: FilterFunc
    name: str


class MacroDef(TypedDict):
    """宏定义

    表示模板中定义的宏的结构.
    """

    params: List[str]  # 宏的参数列表
    content: List[TemplateNode]  # 宏的内容节点列表


class LoopContext(TypedDict):
    """`for` 循环中的 `loop` 变量上下文"""

    index: int  # 从 1 开始的索引
    index0: int  # 从 0 开始的索引
    first: bool  # 是否为第一个元素
    last: bool  # 是否为最后一个元素


RenderContext = Dict[str, object]  # 模板渲染时的上下文变量字典
""" 渲染上下文类型 """


ExpressionResult = Union[str, int, float, bool, List[Any], Dict[str, Any], None]
""" 表达式求值结果类型 """


FilterArg = Union[str, VariableValue]
""" 过滤器参数类型 """

FilterArgs = List[FilterArg]
""" 过滤器参数列表类型 """


class ControlNode(TypedDict):
    """控制结构节点"""

    type: Literal["control"]  # noqa: F821
    content: str
    subtype: Literal["if", "for", "set", "macro", "end"]  # noqa: F821, F722
    condition: Optional[str]  # `if` 条件的表达式
    target: Optional[str]  # `for` 循环的目标变量
    iterable: Optional[str]  # `for` 循环的可迭代对象


__all__ = ()
