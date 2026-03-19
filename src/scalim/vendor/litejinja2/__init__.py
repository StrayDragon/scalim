"""`LiteJinja2` - 简化的 `Jinja2` 兼容子集.

支持的模板语法示例:

- 变量: `{{ variable }}`
- `for` 循环: `{% for item in list %} ... {% endfor %}`
- `if` 条件: `{% if condition %} ... {% else %} ... {% endif %}`
- 过滤器: `{{ variable | filter_name }}`
- 变量赋值: `{% set var = value %}`

当前不支持 `macro`.
"""

# region imports

import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from .typedefs import (
    ExpressionResult,
    FilterFunc,
    LoopContext,
    MacroDef,
    RenderContext,
    TemplateNode,
    VariableValue,
)

# endregion


class TemplateError(Exception):
    """模板相关错误"""


# 内置过滤器
def _filter_length(value: VariableValue) -> int:
    """获取长度.

    参数:
        `value`: 要获取长度的值,支持 `str`/`list`/`tuple`/`dict` 等.

    返回:
        长度值; 若无法获取则返回 `0`.
    """
    try:
        if value is None:
            return 0
        # 确保 `value` 是可测量长度的类型
        if isinstance(value, (str, list, tuple, dict)):
            return len(value)
    except (TypeError, AttributeError):
        return 0
    else:
        return 0


def _filter_default(value: VariableValue, default_value: str = "") -> VariableValue:
    """提供默认值.

    参数:
        `value`: 要检查的值.
        `default_value`: 默认值.

    返回:
        当 `value` 为 `None` 或空字符串时返回 `default_value`, 否则返回 `value`.
    """
    if value is None or value == "":
        return default_value
    return value


def _filter_upper(value: VariableValue) -> str:
    """转大写.

    参数:
        `value`: 要转换的值.

    返回:
        转换为大写的字符串.
    """
    return str(value).upper()


def _filter_lower(value: VariableValue) -> str:
    """转小写.

    参数:
        `value`: 要转换的值.

    返回:
        转换为小写的字符串.
    """
    return str(value).lower()


def _filter_trim(value: VariableValue) -> str:
    """去除首尾空格.

    参数:
        `value`: 要处理的值.

    返回:
        去除首尾空格的字符串.
    """
    return str(value).strip()


# 默认过滤器字典
DEFAULT_FILTERS: Dict[str, Callable[..., Any]] = {
    "length": _filter_length,
    "default": _filter_default,
    "upper": _filter_upper,
    "lower": _filter_lower,
    "trim": _filter_trim,
}


class Template:
    """模板类 - 解析和渲染模板字符串"""

    template_string: str
    nodes: List[TemplateNode]
    filters: Dict[str, FilterFunc]
    macros: Dict[str, MacroDef]

    def __init__(self, template_string: str, filters: Optional[Dict[str, FilterFunc]] = None) -> None:
        """初始化模板.

        参数:
            `template_string`: 模板字符串.
            `filters`: 自定义过滤器字典(可选).
        """
        self.template_string = template_string
        self.filters = {**DEFAULT_FILTERS}
        if filters:
            self.filters.update(filters)
        self.macros = {}
        self.nodes = self._parse()

    def _parse(self) -> List[TemplateNode]:
        """解析模板字符串为节点列表"""
        nodes: List[TemplateNode] = []
        pos = 0

        while pos < len(self.template_string):
            # 查找下一个模板元素
            var_match = re.search(r"\{\{.*?\}\}", self.template_string[pos:])
            control_match = re.search(r"\{%.*?%\}", self.template_string[pos:])

            # 确定下一个元素的类型和位置
            if var_match and control_match:
                if var_match.start() < control_match.start():
                    next_type = "var"
                    next_match = var_match
                else:
                    next_type = "control"
                    next_match = control_match
            elif var_match:
                next_type = "var"
                next_match = var_match
            elif control_match:
                next_type = "control"
                next_match = control_match
            else:
                # 没有更多模板元素,添加剩余文本
                remaining_text = self.template_string[pos:]
                if remaining_text:
                    nodes.append({"type": "text", "content": remaining_text})
                break

            # 添加元素前的文本
            text_before = self.template_string[pos : pos + next_match.start()]
            if text_before:
                nodes.append({"type": "text", "content": text_before})

            # 添加模板元素
            if next_type == "var":
                nodes.append({"type": "var", "content": next_match.group().strip("{}").strip()})
            else:
                content = next_match.group().strip("{%}").strip()
                nodes.append({"type": "control", "content": content})

            # 更新位置
            pos += next_match.end()

        return nodes

    def render(self, context: RenderContext) -> str:
        """渲染模板.

        参数:
            `context`: 上下文变量字典.

        返回:
            渲染后的字符串.
        """
        try:
            return self._render_nodes(self.nodes, context)
        except Exception as e:
            error_msg = f"模板渲染失败: {e}"
            raise TemplateError(error_msg) from e

    def _render_nodes(self, nodes: List[TemplateNode], context: RenderContext) -> str:
        """渲染节点列表"""
        output: List[str] = []
        i = 0

        while i < len(nodes):
            node = nodes[i]

            if node["type"] == "text":
                output.append(node["content"])
            elif node["type"] == "var":
                value = self._get_variable_with_filters(node["content"], context)
                output.append(str(value))
            elif node["type"] == "control":
                # 处理控制结构
                result, consumed = self._handle_control(node, nodes, i, context)
                if result is not None:
                    output.append(result)
                    i += consumed
                    continue

            i += 1

        return "".join(output)

    def _handle_control(self, node: TemplateNode, nodes: List[TemplateNode], pos: int, context: RenderContext) -> Tuple[Optional[str], int]:
        """处理控制结构"""
        content = node["content"]

        if content.startswith("if "):
            return self._handle_if(nodes, pos, context)
        if content.startswith("for "):
            return self._handle_for(nodes, pos, context)
        if content.startswith("set "):
            return self._handle_set(content, context)
        if content.startswith("end"):
            return None, 0

        return None, 0

    def _handle_if(self, nodes: List[TemplateNode], pos: int, context: RenderContext) -> Tuple[str, int]:
        """处理 `if` 条件结构."""
        condition = nodes[pos]["content"][3:].strip()
        condition_result = self._evaluate_condition(condition, context)

        else_pos, end_pos = self._find_if_end(nodes, pos)

        # 选择要渲染的节点
        if condition_result:
            start = pos + 1
            end = else_pos if else_pos is not None else end_pos
        elif else_pos is not None:
            start = else_pos + 1
            end = end_pos
        else:
            start = end_pos + 1
            end = end_pos

        # 渲染选中的节点
        result = self._render_nodes(nodes[start:end], context) if start < end else ""

        return result, end_pos - pos + 1

    def _find_if_end(self, nodes: List[TemplateNode], pos: int) -> Tuple[Optional[int], int]:
        """查找 `if` 语句的结束位置."""
        else_pos = None
        depth = 1

        for i in range(pos + 1, len(nodes)):
            if nodes[i]["type"] != "control":
                continue

            content = nodes[i]["content"]
            if content.startswith("if "):
                depth += 1
            elif content == "endif":
                depth -= 1
                if depth == 0:
                    return else_pos, i
            elif content == "else" and depth == 1:
                else_pos = i

        error_msg = "未找到对应的 `endif`"
        raise TemplateError(error_msg)

    def _handle_for(self, nodes: List[TemplateNode], pos: int, context: RenderContext) -> Tuple[str, int]:  # noqa: C901, PLR0912
        """处理 `for` 循环结构"""
        # 解析 `for` 循环
        for_content = nodes[pos]["content"][4:].strip()
        if " in " not in for_content:
            error_msg = f"无效的 `for` 循环语法: {for_content}"
            raise TemplateError(error_msg)

        var_part, iter_part = for_content.split(" in ", 1)
        var_part = var_part.strip()
        iter_expr = iter_part.strip()

        # 支持元组解包: `for x, y in items`
        var_names = [v.strip() for v in var_part.split(",")]

        # 获取可迭代对象
        iterable = self._get_variable(iter_expr, context)
        # 检查是否可迭代
        if not isinstance(iterable, (list, tuple, dict, str)) and not hasattr(iterable, "__iter__"):
            msg = f"'{iter_expr}' 不可迭代"
            raise TemplateError(msg)

        # 转换为列表以便计算长度
        try:
            # 确保 `iterable` 是可迭代的(排除基本类型)
            if isinstance(iterable, (int, float, bool, type(None))):
                msg = f"'{iter_expr}' 不是可迭代类型"
                raise TemplateError(msg)
            iterable = list(iterable)
        except TypeError as e:
            msg = f"'{iter_expr}' 无法转换为列表"
            raise TemplateError(msg) from e

        # 查找对应的 `endfor`
        end_pos = None
        depth = 1
        for i in range(pos + 1, len(nodes)):
            if nodes[i]["type"] == "control":
                content = nodes[i]["content"]
                if content.startswith("for "):
                    depth += 1
                elif content == "endfor":
                    depth -= 1
                    if depth == 0:
                        end_pos = i
                        break

        if end_pos is None:
            msg = "未找到对应的 `endfor`"
            raise TemplateError(msg)

        # 渲染循环内容
        loop_nodes = nodes[pos + 1 : end_pos]
        output_parts = []

        for index, item in enumerate(iterable):
            # 创建循环上下文
            loop_ctx: Dict[str, Union[VariableValue, LoopContext]] = {
                "loop": {
                    "index": index + 1,
                    "index0": index,
                    "first": index == 0,
                    "last": index == len(iterable) - 1,
                },
            }

            # 处理变量赋值 - 支持元组解包
            if len(var_names) == 1:
                # 单个变量: `for item in items`
                loop_ctx[var_names[0]] = item
            # 元组解包: `for x, y in items`
            elif isinstance(item, (tuple, list)) and len(item) >= len(var_names):
                for i, var_name in enumerate(var_names):
                    loop_ctx[var_name] = item[i]
            else:
                # 如果不是元组/列表,尝试解包
                try:
                    unpacked = list(item)
                    for i, var_name in enumerate(var_names):
                        loop_ctx[var_name] = unpacked[i] if i < len(unpacked) else ""
                except (TypeError, IndexError):
                    # 解包失败,使用空值
                    for var_name in var_names:
                        loop_ctx[var_name] = ""

            # 合并上下文
            merged_context = {**context, **loop_ctx}

            # 渲染循环体
            output_parts.append(self._render_nodes(loop_nodes, merged_context))  # pyright: ignore[reportUnknownMemberType]

        return "".join(output_parts), end_pos - pos + 1  # pyright: ignore[reportUnknownArgumentType]

    def _handle_set(self, content: str, context: RenderContext) -> Tuple[None, int]:
        """处理 `set` 语句.

        支持语法示例:

        - `{% set var = value %}`
        - `{% set var = "string" %}`
        - `{% set var = other_var %}`
        - `{% set var = other_var | filter %}`
        - `{% set var = "prefix_" + other_var %}`
        """
        # 解析 `set` 语句: `set var = value`
        set_content = content[4:].strip()  # 移除 `set ` 前缀

        if "=" not in set_content:
            error_msg = f"无效的 `set` 语法: {set_content}"
            raise TemplateError(error_msg)

        var_name, value_expr = set_content.split("=", 1)
        var_name = var_name.strip()
        value_expr = value_expr.strip()

        # 计算值
        value = self._evaluate_expression(value_expr, context)

        # 设置变量到上下文
        context[var_name] = value

        # `set` 语句不产生输出
        return None, 0

    def _evaluate_expression(self, expr: str, context: RenderContext) -> ExpressionResult:
        """评估表达式,支持字符串拼接与过滤器.

        支持的表达式示例:

        - 字符串字面量: `"string"`
        - 数字字面量: `123`
        - 变量: `variable`
        - 带过滤器的变量: `variable | filter`
        - 字符串拼接: `"prefix_" + variable`
        - 变量拼接字符串: `variable + "_suffix"`

        参数:
            `expr`: 要评估的表达式字符串.
            `context`: 渲染上下文变量字典.

        返回:
            表达式求值结果,类型可能是 `str`/`int` 或 `VariableValue`.
        """
        expr = expr.strip()

        # 1. 字符串字面量
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # 2. 数字字面量
        if expr.isdigit():
            return int(expr)

        # 3. 字符串拼接: 支持 `"a" + b` / `a + "b"` / `a + b` 等形式
        if "+" in expr:
            parts = expr.split("+")
            result_parts: List[str] = []
            for _part in parts:
                part = _part.strip()
                # 递归评估每个部分
                part_value = self._evaluate_expression(part, context)
                result_parts.append(str(part_value))
            return "".join(result_parts)

        # 4. 变量或表达式 (支持过滤器)
        return self._get_variable_with_filters(expr, context)

    def _get_variable_with_filters(self, var_expr: str, context: RenderContext) -> VariableValue:
        """获取变量值并应用过滤器.

        支持语法示例: `variable | filter1 | filter2(arg)`.

        参数:
            `var_expr`: 变量表达式,可能包含过滤器链.
            `context`: 渲染上下文变量字典.

        返回:
            变量值经过过滤器处理后的结果,类型取决于变量与过滤器.
        """
        # 分割变量和过滤器
        if "|" not in var_expr:
            return self._get_variable(var_expr, context)

        parts = var_expr.split("|")
        var_name = parts[0].strip()

        # 获取初始值
        value = self._get_variable(var_name, context)

        # 依次应用过滤器
        for _filter_expr in parts[1:]:
            filter_expr = _filter_expr.strip()

            # 解析过滤器名称和参数
            if "(" in filter_expr:
                # 带参数的过滤器: `filter(arg1, arg2)`
                filter_name = filter_expr[: filter_expr.index("(")].strip()
                args_str = filter_expr[filter_expr.index("(") + 1 : filter_expr.rindex(")")].strip()

                # 解析参数
                args: List[Union[str, VariableValue]] = []
                if args_str:
                    for _arg in args_str.split(","):
                        arg = _arg.strip()
                        # 移除引号
                        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
                            args.append(arg[1:-1])
                        else:
                            # 尝试作为变量解析
                            args.append(self._get_variable(arg, context))
            else:
                # 无参数的过滤器
                filter_name = filter_expr
                args = []

            # 应用过滤器
            if filter_name in self.filters:
                filter_func = self.filters[filter_name]
                try:
                    value = filter_func(value, *args)
                except Exception as e:
                    error_msg = f"过滤器 '{filter_name}' 执行失败: {e}"
                    raise TemplateError(error_msg) from e
            else:
                error_msg = f"未知的过滤器: {filter_name}"
                raise TemplateError(error_msg)

        return value

    def _get_variable(self, var_expr: str, context: RenderContext) -> VariableValue:  # noqa: C901, PLR0911, PLR0912, PLR0915
        """获取变量值,支持点号访问、方法调用和下标访问.

        参数:
            `var_expr`: 变量表达式.
            `context`: 渲染上下文变量字典.

        返回:
            变量值; 如果未找到则返回空字符串.

        说明:
            支持以下访问模式:
            - 简单变量名: `name`
            - 属性访问: `user.name`
            - 方法调用: `user.get_name()`
            - 字典下标: `config["key"]` 或 `dict.key`
            - 列表下标: `items[0]`
        """
        var_expr = var_expr.strip()

        # 处理字典下标访问: `dict[key]`
        if "[" in var_expr and "]" in var_expr:
            # 解析 `dict[key]` 语法
            bracket_start = var_expr.index("[")
            bracket_end = var_expr.rindex("]")

            base_expr = var_expr[:bracket_start]
            key_expr = var_expr[bracket_start + 1 : bracket_end]

            # 获取基础对象
            base_value = self._get_variable(base_expr, context) if base_expr else context

            # 获取键值
            # 移除引号(如果有)
            if (key_expr.startswith('"') and key_expr.endswith('"')) or (key_expr.startswith("'") and key_expr.endswith("'")):
                key = key_expr[1:-1]
            else:
                # 作为变量解析
                key = self._get_variable(key_expr, context)

            # 访问字典或列表
            try:
                if isinstance(base_value, dict):
                    # 确保 `key` 是字符串类型
                    str_key = str(key) if not isinstance(key, str) else key
                    return base_value.get(str_key, "")
                if isinstance(base_value, (list, tuple)):
                    # 确保 `key` 可以转换为整数
                    if isinstance(key, int):
                        return base_value[key]
                    if isinstance(key, str) and key.isdigit():
                        return base_value[int(key)]
            except (KeyError, IndexError, ValueError):
                return ""
            else:
                return ""

        # 处理简单的变量名
        if "." not in var_expr and " " not in var_expr:
            if var_expr in context:
                return context[var_expr]
            return ""

        # 处理带点号的属性访问和方法调用
        parts = var_expr.split(".")
        value = context

        for part in parts:
            # 检查是否是方法调用 (以 () 结尾)
            if part.endswith("()"):
                method_name = part[:-2]
                if isinstance(value, dict):
                    if method_name in value:
                        value = value[method_name]
                    elif hasattr(value, method_name):
                        method = getattr(value, method_name)
                        if callable(method):
                            value = method()
                        else:
                            value = method
                    else:
                        return ""
                elif hasattr(value, method_name):
                    method = getattr(value, method_name)
                    if callable(method):
                        value = method()
                    else:
                        value = method
                else:
                    return ""
            # 普通属性访问
            elif isinstance(value, dict):
                if part in value:
                    value = value[part]
                else:
                    return ""
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return ""

        # 确保返回正确的类型
        result = value if value is not None else ""  # pyright: ignore[reportUnknownVariableType]
        # 使用 `cast` 确保返回 `VariableValue` 类型
        return cast("VariableValue", result)

    def _evaluate_condition(self, condition: str, context: RenderContext) -> bool:  # noqa: PLR0911
        """评估条件表达式.

        参数:
            `condition`: 条件表达式字符串.
            `context`: 渲染上下文变量字典.

        返回:
            条件的布尔结果.

        说明:
            支持简单的条件表达式,例如:

            - 变量存在性检查: `var`
            - 相等比较: `var == value`
            - 不等比较: `var != value`
            - 布尔值: `True`/`False`
        """
        # 简单的条件评估
        condition = condition.strip()

        # 处理 `is defined`
        if condition.endswith(" is defined"):
            var_name = condition[:-10].strip()
            return var_name in context

        # 处理 `is not defined`
        if condition.endswith(" is not defined"):
            var_name = condition[:-14].strip()
            return var_name not in context

        # 处理 `not`
        if condition.startswith("not "):
            return not self._evaluate_condition(condition[4:].strip(), context)

        # 处理 `and`
        if " and " in condition:
            parts = condition.split(" and ")
            return all(self._evaluate_condition(part.strip(), context) for part in parts)

        # 处理 `or`
        if " or " in condition:
            parts = condition.split(" or ")
            return any(self._evaluate_condition(part.strip(), context) for part in parts)

        # 处理简单的变量比较
        value = self._get_variable(condition, context)
        if value != "":
            return bool(value)

        # 默认返回 `False`
        return False


class Environment:
    """模板环境管理器"""

    _cache: Dict[str, Template]

    def __init__(self) -> None:
        self._cache = {}

    def from_string(self, template_string: str) -> Template:
        """从字符串创建模板"""
        # 简单的缓存机制
        if template_string in self._cache:
            return self._cache[template_string]

        template = Template(template_string)
        self._cache[template_string] = template
        return template

    def clear_cache(self) -> None:
        self._cache.clear()


# 全局环境实例
_default_env = Environment()


def from_string(template_string: str) -> Template:
    """从字符串创建模板的便捷函数"""
    return _default_env.from_string(template_string)


def clear_cache() -> None:
    """清除全局缓存的便捷函数"""
    _default_env.clear_cache()


__all__ = [
    "Environment",
    "Template",
    "TemplateError",
    "clear_cache",
    "from_string",
]
