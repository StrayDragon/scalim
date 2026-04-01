import ast
import hashlib
import logging
import operator
import sys
import threading
from collections import OrderedDict
from decimal import Decimal
from types import CodeType
from typing import Any, Callable, ClassVar, Container, Dict, FrozenSet, List, Optional, Set, Tuple, Type, Union, cast

from .....exceptions import ScalimYamlError
from .....secure_compute_contracts import (
    SecureComputeCalculatorContract,
)
from .....secure_compute_contracts import (
    is_secure_compute_calculator as _is_secure_compute_calculator,
)
from .....vendor.compact.typing_extensionsx import override
from .....vendor.dataclassesx import dataclass

_PY38_PLUS = sys.version_info >= (3, 8)

security_logger = logging.getLogger("scalim.dsl.by_yaml.security")

EVAL_AUDIT_LOG_PREFIX = "求值审计"
EVAL_AUDIT_LOG = EVAL_AUDIT_LOG_PREFIX + ": 表达式=%r, 字段=%r, 结果=%r"

SECURITY_AUDIT_RESOLVED_REFERENCE_PREFIX = "已解析引用"
SECURITY_AUDIT_RESOLVED_REFERENCE_LOG = SECURITY_AUDIT_RESOLVED_REFERENCE_PREFIX + ": %s"

SECURITY_AUDIT_FAILED_RESOLVE_PREFIX = "解析引用失败"
SECURITY_AUDIT_FAILED_RESOLVE_LOG = SECURITY_AUDIT_FAILED_RESOLVE_PREFIX + ": %s - 错误: %s"

SECURITY_AUDIT_SECURITY_VIOLATION_PREFIX = "触发安全违规"
SECURITY_AUDIT_SECURITY_VIOLATION_LOG = "引用 '%s' 触发安全违规[%s]: %s"

SECURITY_AUDIT_EXPRESSION_VALID_PREFIX = "表达式校验通过"
SECURITY_AUDIT_EXPRESSION_VALID_LOG = SECURITY_AUDIT_EXPRESSION_VALID_PREFIX + ": %s"

SECURITY_AUDIT_INVALID_EXPRESSION_PREFIX = "无效表达式"
SECURITY_AUDIT_INVALID_EXPRESSION_LOG = SECURITY_AUDIT_INVALID_EXPRESSION_PREFIX + ": %s - 错误: %s"


class _NameCollector(ast.NodeVisitor):
    _builtin_names: FrozenSet[str]
    _seen_order: List[str]
    _seen_set: Set[str]

    def __init__(self, builtin_names: FrozenSet[str]) -> None:
        self._builtin_names = builtin_names
        self._seen_order = []
        self._seen_set = set()

    @override
    def visit_Name(self, node: ast.Name) -> None:
        name = node.id
        if name not in self._builtin_names and name not in self._seen_set:
            self._seen_order.append(name)
            self._seen_set.add(name)
        self.generic_visit(node)

    def get_dependencies(self) -> Tuple[str, ...]:
        return tuple(self._seen_order)


def extract_dependencies_from_compute(expression: str, builtin_names: FrozenSet[str]) -> Tuple[str, ...]:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return ()

    collector = _NameCollector(builtin_names)
    collector.visit(tree)
    return collector.get_dependencies()


def is_constant_compute_expression(expression: str) -> bool:
    """判断表达式是否为“纯字面量”计算.

    当计算表达式满足以下条件时返回 `True`:
    - 不依赖任何字段(因此名称收集结果为空)
    - 不包含任何 `Name`/`Call` 节点(包括类似 `int(...)` 的内置函数调用)
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return False

    return all(not isinstance(node, (ast.Name, ast.Call)) for node in ast.walk(tree))


def _not_in(a: Container[Any], b: Any) -> bool:
    return not operator.contains(a, b)


class ScalimSecurityError(ScalimYamlError):
    pass


class ScalimComputeExpressionError(ScalimYamlError):
    pass


AuditCallback = Callable[[str, Dict[str, Any], Any], None]


@dataclass(frozen=True)
class ComputeLimits:
    max_expression_len: int = 2048
    max_ast_nodes: int = 2000
    max_ast_depth: int = 40
    max_literal_string_len: int = 4096
    max_collection_literal_len: int = 1000
    max_repeat: int = 1000
    max_range_len: int = 10000


@dataclass(frozen=True)
class SecureComputeCalculator(SecureComputeCalculatorContract):
    engine: "SecureComputeEngine"
    expression: str
    dependencies: Tuple[str, ...]
    code: CodeType

    @override
    def __call__(self, *args: Any, **field_values: Any) -> Any:
        return self.engine.evaluate_compiled(
            expression=self.expression,
            code=self.code,
            dependencies=self.dependencies,
            args=args,
            field_values=field_values,
        )


def is_secure_compute_calculator(value: object) -> bool:
    return _is_secure_compute_calculator(value)


def default_audit_callback(expression: str, field_values: Dict[str, Any], result: Any) -> None:
    # 注意: 这里会记录原始字段值与计算结果;根据输入数据集不同,可能包含 `PII` 或其他敏感信息.
    # 在生产环境中,除非你完全信任数据,否则建议使用脱敏回调(或直接禁用审计日志).
    security_logger.debug(EVAL_AUDIT_LOG, expression, field_values, result)


def redacted_audit_callback(expression: str, field_values: Dict[str, Any], result: Any) -> None:
    """脱敏审计回调: 仅记录表达式和字段名,不记录字段值与结果."""
    expr_id = hashlib.sha256(expression.encode("utf-8")).hexdigest()[:12]
    field_names = sorted(field_values.keys()) if field_values else []
    security_logger.debug(
        "%s: `expr_hash`=%s, `fields`=%r, `result_type`=%s",
        EVAL_AUDIT_LOG_PREFIX,
        expr_id,
        field_names,
        type(result).__name__,
    )


def _safe_decimal_helper(value: Any) -> Optional[Decimal]:
    from ...runtime._internal.conversion_lookup import cast_decimal  # noqa: PLC0415

    return cast_decimal(value)


class ExpressionValidator:
    _allowed_names: Set[str]
    _allowed_functions: FrozenSet[str]
    _safe_operators: Dict[Type[ast.operator], Callable[..., Any]]
    _safe_unary: Dict[Type[ast.unaryop], Callable[..., Any]]
    _safe_comparators: Dict[Type[ast.cmpop], Callable[..., bool]]
    _forbidden_names: FrozenSet[str]
    _handlers: Dict[Type[ast.AST], Callable[[ast.AST], None]]

    def __init__(
        self,
        allowed_names: Set[str],
        allowed_functions: FrozenSet[str],
        safe_operators: Dict[Type[ast.operator], Callable[..., Any]],
        safe_unary: Dict[Type[ast.unaryop], Callable[..., Any]],
        safe_comparators: Dict[Type[ast.cmpop], Callable[..., bool]],
        forbidden_names: FrozenSet[str],
    ) -> None:
        self._allowed_names = allowed_names
        self._allowed_functions = allowed_functions
        self._safe_operators = safe_operators
        self._safe_unary = safe_unary
        self._safe_comparators = safe_comparators
        self._forbidden_names = forbidden_names
        self._handlers = {
            ast.Name: self._validate_name_node,
            ast.BinOp: self._validate_binop_node,
            ast.UnaryOp: self._validate_unaryop_node,
            ast.Compare: self._validate_compare_node,
            ast.IfExp: self._validate_ifexp_node,
            ast.Call: self._validate_call_node,
            ast.Attribute: self._validate_attribute_node,
            ast.BoolOp: self._validate_boolop_node,
            ast.List: self._validate_sequence_node,
            ast.Tuple: self._validate_sequence_node,
        }

    def validate(self, node: ast.AST) -> None:
        self._visit(node)

    def _visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            return
        if not _PY38_PLUS and isinstance(
            node,
            (
                ast.Str,
                ast.Num,
                ast.Bytes,
                ast.NameConstant,
            ),
        ):  # pragma: no cover  # pragma: allow-no-cover py<3.8 legacy AST nodes
            return  # pragma: no cover  # pragma: allow-no-cover py<3.8 legacy AST nodes

        handler = self._handlers.get(type(node))
        if handler is None:
            msg = "Unsupported AST node type: {}".format(type(node).__name__)
            raise ScalimSecurityError(msg)
        handler(node)

    def _validate_name_node(self, node: ast.AST) -> None:
        typed = cast("ast.Name", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        name = typed.id
        if name in self._forbidden_names:
            msg = "Forbidden name '{}' in expression".format(name)
            raise ScalimSecurityError(msg)
        if name not in self._allowed_names and name not in self._allowed_functions:
            msg = "Unknown name '{}' in expression. Allowed: {}".format(name, ", ".join(sorted(self._allowed_names)))
            raise ScalimSecurityError(msg)

    def _validate_binop_node(self, node: ast.AST) -> None:
        typed = cast("ast.BinOp", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        if type(typed.op) not in self._safe_operators:
            msg = "Unsupported operator: {}".format(type(typed.op).__name__)
            raise ScalimSecurityError(msg)
        self._visit(typed.left)
        self._visit(typed.right)

    def _validate_unaryop_node(self, node: ast.AST) -> None:
        typed = cast("ast.UnaryOp", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        if type(typed.op) not in self._safe_unary:  # pragma: no cover  # pragma: allow-no-cover invariant: unaryop exhaustively allowlisted
            msg = "Unsupported unary operator: {}".format(
                type(typed.op).__name__
            )  # pragma: no cover  # pragma: allow-no-cover invariant: unaryop exhaustively allowlisted
            raise ScalimSecurityError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: unaryop exhaustively allowlisted
        self._visit(typed.operand)

    def _validate_compare_node(self, node: ast.AST) -> None:
        typed = cast("ast.Compare", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        self._visit(typed.left)
        for comp in typed.comparators:
            self._visit(comp)
        for op in typed.ops:
            if type(op) not in self._safe_comparators:
                msg = "Unsupported comparator: {}".format(type(op).__name__)
                raise ScalimSecurityError(msg)

    def _validate_ifexp_node(self, node: ast.AST) -> None:
        typed = cast("ast.IfExp", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        self._visit(typed.test)
        self._visit(typed.body)
        self._visit(typed.orelse)

    def _validate_call_node(self, node: ast.AST) -> None:
        typed = cast("ast.Call", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        if isinstance(typed.func, ast.Attribute):
            msg = (
                "Method calls (attribute calls) are not allowed in compute expressions "
                "(e.g. obj.get(...), s.strip(...)); move this logic to call_by "
                '(allowlisted), e.g. call_by: "myapp.module:fn(value=value, ctx=$ctx)"'
            )
            raise ScalimSecurityError(msg)
        if not isinstance(typed.func, ast.Name):
            msg = "Only simple function calls are allowed (use call_by for complex logic)"
            raise ScalimSecurityError(msg)
        func_name = typed.func.id
        if func_name not in self._allowed_functions:
            msg = "Function '{}' is not in the allowed list".format(func_name)
            raise ScalimSecurityError(msg)
        for arg in typed.args:
            self._visit(arg)
        if typed.keywords:
            msg = "Keyword arguments are not allowed in expressions"
            raise ScalimSecurityError(msg)

    def _validate_attribute_node(self, node: ast.AST) -> None:
        typed = cast("ast.Attribute", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        msg = (
            "Attribute access is not allowed in compute expressions (got attribute={!r}); "
            'move this logic to call_by (allowlisted), e.g. call_by: "myapp.module:fn(value=value, ctx=$ctx)"'
        ).format(str(typed.attr))
        raise ScalimSecurityError(msg)

    def _validate_boolop_node(self, node: ast.AST) -> None:
        typed = cast("ast.BoolOp", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        for value in typed.values:
            self._visit(value)

    def _validate_sequence_node(self, node: ast.AST) -> None:
        typed = cast("Union[ast.List, ast.Tuple]", node)  # pragma: allow-cast ast handler dispatch typed narrowing
        for elt in typed.elts:
            self._visit(elt)


class SecureComputeEngine:
    # 二元运算符: +, -, *, /, //, %, **
    SAFE_OPERATORS: ClassVar[Dict[Type[ast.operator], Callable[..., Any]]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    # 一元运算符: -, +, ~, `not`
    SAFE_UNARY_OPERATORS: ClassVar[Dict[Type[ast.unaryop], Callable[..., Any]]] = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.Invert: operator.invert,
        ast.Not: operator.not_,
    }

    # 比较运算符: ==, !=, <, <=, >, >=, `in`, `not in`, `is`, `is not`
    SAFE_COMPARATORS: ClassVar[Dict[Type[ast.cmpop], Callable[..., bool]]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: operator.contains,
        ast.NotIn: _not_in,
        ast.Is: operator.is_,
        ast.IsNot: operator.is_not,
    }

    SAFE_FUNCTIONS: ClassVar[Dict[str, Callable[..., Any]]] = {
        # 类型转换
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        # 金融场景常用: 允许在表达式中使用 `Decimal("0.1")`,避免 `float` 精度问题
        "Decimal": Decimal,
        "dec": _safe_decimal_helper,
        "list": list,
        "tuple": tuple,
        "set": set,
        "dict": dict,
        # 数学函数
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "round": round,
        "pow": pow,
        "divmod": divmod,
        # 序列函数
        "len": len,
        "sorted": sorted,
        "reversed": reversed,
        "enumerate": enumerate,
        "zip": zip,
        "range": range,
        "all": all,
        "any": any,
        "filter": filter,
        "map": map,
        # 字符串函数
        "ord": ord,
        "chr": chr,
        "repr": repr,
        "format": format,
        # 类型检查
        "isinstance": isinstance,
        "type": type,
    }
    SAFE_BUILTINS: ClassVar[FrozenSet[str]] = frozenset(SAFE_FUNCTIONS)

    FORBIDDEN_NAMES: ClassVar[FrozenSet[str]] = frozenset(
        [
            "__import__",
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "globals",
            "locals",
            "vars",
            "dir",
            "getattr",
            "setattr",
            "delattr",
            "hasattr",
            "__builtins__",
            "__class__",
            "__bases__",
            "__mro__",
            "__subclasses__",
            "__code__",
            "__globals__",
        ]
    )
    DEFAULT_COMPILED_CACHE_MAX_SIZE: ClassVar[int] = 256

    _allowed_functions: FrozenSet[str]
    _custom_functions: Dict[str, Callable[..., Any]]
    _audit_callback: Optional["AuditCallback"]
    _compiled_cache: "OrderedDict[str, SecureComputeCalculator]"
    _compiled_cache_max_size: int
    _compiled_cache_lock: threading.Lock
    _limits: ComputeLimits

    def __init__(
        self,
        allowed_functions: Optional[FrozenSet[str]] = None,
        allowed_function_map: Optional[Dict[str, Callable[..., Any]]] = None,
        audit_callback: Optional["AuditCallback"] = None,
        limits: Optional[ComputeLimits] = None,
        max_compiled_cache_size: int = DEFAULT_COMPILED_CACHE_MAX_SIZE,
    ) -> None:
        if max_compiled_cache_size < 1:
            msg = "max_compiled_cache_size must be >= 1"
            raise ValueError(msg)

        self._limits = limits or ComputeLimits()
        self._validate_limits()
        self._custom_functions = dict(allowed_function_map) if allowed_function_map else {}
        allowed = set(self.SAFE_BUILTINS if allowed_functions is None else allowed_functions)
        if self._custom_functions:
            allowed.update(self._custom_functions.keys())
        self._allowed_functions = frozenset(allowed)
        self._compiled_cache_max_size = max_compiled_cache_size
        self._compiled_cache = OrderedDict()
        self._compiled_cache_lock = threading.Lock()
        self._audit_callback = audit_callback

    def _validate_limits(self) -> None:
        limits = self._limits
        for name, value in (
            ("max_expression_len", limits.max_expression_len),
            ("max_ast_nodes", limits.max_ast_nodes),
            ("max_ast_depth", limits.max_ast_depth),
            ("max_literal_string_len", limits.max_literal_string_len),
            ("max_collection_literal_len", limits.max_collection_literal_len),
            ("max_repeat", limits.max_repeat),
            ("max_range_len", limits.max_range_len),
        ):
            numeric_value = int(value)
            if numeric_value < 0:
                msg = "ComputeLimits.{} must be >= 0".format(name)
                raise ValueError(msg)

    def compile(self, expression: str, dependencies: Tuple[str, ...]) -> SecureComputeCalculator:
        cache_key = "{}:{}".format(expression, ",".join(dependencies))
        with self._compiled_cache_lock:
            cached = self._compiled_cache.get(cache_key)
            if cached is not None:
                self._compiled_cache.move_to_end(cache_key)
                return cached

        tree = self._validate_expression(expression, dependencies)
        code = compile(tree, "<scalim-compute>", "eval")
        calculator = SecureComputeCalculator(
            engine=self,
            expression=expression,
            dependencies=dependencies,
            code=code,
        )

        with self._compiled_cache_lock:
            self._compiled_cache[cache_key] = calculator
            if len(self._compiled_cache) > self._compiled_cache_max_size:
                _ = self._compiled_cache.popitem(last=False)
        return calculator

    def _validate_expression(self, expression: str, dependencies: Tuple[str, ...]) -> ast.Expression:
        if len(expression) > int(self._limits.max_expression_len):
            msg = "Compute expression exceeds max_expression_len (len={}, limit={})".format(
                len(expression),
                int(self._limits.max_expression_len),
            )
            raise ScalimComputeExpressionError(msg)

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            msg = "Invalid expression syntax: {}".format(e)
            raise ScalimComputeExpressionError(msg) from e

        self._enforce_ast_limits(tree)

        validator = ExpressionValidator(
            allowed_names=set(dependencies),
            allowed_functions=self._allowed_functions,
            safe_operators=self.SAFE_OPERATORS,
            safe_unary=self.SAFE_UNARY_OPERATORS,
            safe_comparators=self.SAFE_COMPARATORS,
            forbidden_names=self.FORBIDDEN_NAMES,
        )
        validator.validate(tree.body)
        return tree

    def evaluate_compiled(
        self,
        *,
        expression: str,
        code: CodeType,
        dependencies: Tuple[str, ...],
        args: Tuple[Any, ...],
        field_values: Dict[str, Any],
    ) -> Any:
        if args:
            if field_values:
                msg = "Secure compute calculator does not accept mixed args and kwargs"
                raise TypeError(msg)
            if len(args) != len(dependencies):
                msg = "Secure compute calculator expected {} positional args, got {}".format(len(dependencies), len(args))
                raise TypeError(msg)
            return self._evaluate_positional(expression, code, dependencies, args)
        return self._evaluate(expression, code, field_values)

    @staticmethod
    def _as_int_literal(node: ast.AST) -> Optional[int]:
        try:
            value = ast.literal_eval(node)
        except (SyntaxError, ValueError):
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return int(value)
        return None

    @staticmethod
    def _string_literal_len(node: ast.AST) -> Optional[int]:
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, (str, bytes)):
                return len(value)
            return None
        if not _PY38_PLUS and isinstance(node, (ast.Str, ast.Bytes)):  # pragma: no cover  # pragma: allow-no-cover py<3.8 legacy AST nodes
            literal = cast(
                "Union[str, bytes]", node.s
            )  # pragma: no cover  # pragma: allow-no-cover py<3.8  # pragma: allow-cast py<3.8 ast.Str/Bytes .s
            return len(literal)  # pragma: no cover  # pragma: allow-no-cover py<3.8 legacy AST nodes
        return None

    @staticmethod
    def _is_repeatable_literal(node: ast.AST) -> bool:
        if isinstance(node, (ast.List, ast.Tuple)):
            return True
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (str, bytes))
        return not _PY38_PLUS and isinstance(
            node, (ast.Str, ast.Bytes)
        )  # pragma: no cover  # pragma: allow-no-cover py<3.8 legacy AST nodes

    @staticmethod
    def _check_collection_literal_limit(node: ast.AST, max_collection_literal_len: int) -> None:
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) > max_collection_literal_len:
            msg = "Compute expression exceeds max_collection_literal_len (len={}, limit={})".format(
                len(node.elts),
                max_collection_literal_len,
            )
            raise ScalimComputeExpressionError(msg)

    @classmethod
    def _check_repeat_limit(cls, node: ast.AST, max_repeat: int) -> None:
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)):
            return
        left_repeat = cls._as_int_literal(node.left)
        right_repeat = cls._as_int_literal(node.right)
        if left_repeat is not None and cls._is_repeatable_literal(node.right) and left_repeat > max_repeat:
            msg = "Compute expression exceeds max_repeat (repeat={}, limit={})".format(left_repeat, max_repeat)
            raise ScalimComputeExpressionError(msg)
        if right_repeat is not None and cls._is_repeatable_literal(node.left) and right_repeat > max_repeat:
            msg = "Compute expression exceeds max_repeat (repeat={}, limit={})".format(right_repeat, max_repeat)
            raise ScalimComputeExpressionError(msg)

    @classmethod
    def _check_static_range_limit(cls, node: ast.AST, max_range_len: int) -> None:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
            and not node.keywords
            and len(node.args) in (1, 2, 3)
        ):
            return

        args = [cls._as_int_literal(arg) for arg in node.args]
        if not all(arg is not None for arg in args):
            return

        try:
            range_len = len(range(*cast("Tuple[int, ...]", tuple(args))))  # pragma: allow-cast args not-none guard typed narrowing
        except (OverflowError, TypeError, ValueError):
            return

        if range_len > max_range_len:
            msg = "Compute expression exceeds max_range_len (len={}, limit={})".format(range_len, max_range_len)
            raise ScalimComputeExpressionError(msg)

    def _enforce_ast_limits(self, tree: ast.Expression) -> None:
        limits = self._limits
        max_nodes = int(limits.max_ast_nodes)
        max_depth = int(limits.max_ast_depth)
        max_literal_string_len = int(limits.max_literal_string_len)
        max_collection_literal_len = int(limits.max_collection_literal_len)
        max_repeat = int(limits.max_repeat)
        max_range_len = int(limits.max_range_len)

        node_count = 0
        stack: List[Tuple[ast.AST, int]] = [(tree, 1)]
        while stack:
            node, depth = stack.pop()
            node_count += 1
            if node_count > max_nodes:
                msg = "Compute expression exceeds max_ast_nodes (nodes={}, limit={})".format(node_count, max_nodes)
                raise ScalimComputeExpressionError(msg)
            if depth > max_depth:
                msg = "Compute expression exceeds max_ast_depth (depth={}, limit={})".format(depth, max_depth)
                raise ScalimComputeExpressionError(msg)

            literal_len = self._string_literal_len(node)
            if literal_len is not None and literal_len > max_literal_string_len:
                msg = "Compute expression exceeds max_literal_string_len (len={}, limit={})".format(
                    literal_len,
                    max_literal_string_len,
                )
                raise ScalimComputeExpressionError(msg)

            self._check_collection_literal_limit(node, max_collection_literal_len)
            self._check_repeat_limit(node, max_repeat)
            self._check_static_range_limit(node, max_range_len)

            for child in ast.iter_child_nodes(node):
                stack.append((child, depth + 1))

    def _safe_range(self, *args: Any) -> range:
        rng = range(*args)  # type: ignore[arg-type]
        max_range_len = int(self._limits.max_range_len)
        rng_len = len(rng)
        if rng_len > max_range_len:
            msg = "`range` 长度 {} 超过 max_range_len={}".format(rng_len, max_range_len)
            raise ScalimComputeExpressionError(msg)
        return rng

    def _evaluate(self, expression: str, code: Any, field_values: Dict[str, Any]) -> Any:
        safe_globals: Dict[str, Any] = {
            "__builtins__": {},
            # 常量
            "True": True,
            "False": False,
            "None": None,
        }
        safe_globals.update(
            {
                name: (self._safe_range if name == "range" else func)
                for name, func in self.SAFE_FUNCTIONS.items()
                if name in self._allowed_functions
            }
        )
        if self._custom_functions:
            safe_globals.update(self._custom_functions)
        safe_globals.update(field_values)

        try:
            result = eval(code, safe_globals, {})  # noqa: S307
            if self._audit_callback is not None:
                self._audit_callback(expression, field_values, result)
        except ScalimComputeExpressionError:
            raise
        except Exception as e:
            expr_id = hashlib.sha256(expression.encode("utf-8")).hexdigest()[:12]
            security_logger.exception("表达式求值失败: expr_hash=%s", expr_id)
            msg = "表达式求值失败 [expr:{}]: {}".format(expr_id, type(e).__name__)
            raise ScalimComputeExpressionError(msg) from e
        else:
            return result

    def _evaluate_positional(self, expression: str, code: Any, dep_keys: Tuple[str, ...], dep_values: Tuple[Any, ...]) -> Any:
        safe_globals: Dict[str, Any] = {
            "__builtins__": {},
            # 常量
            "True": True,
            "False": False,
            "None": None,
        }
        safe_globals.update(
            {
                name: (self._safe_range if name == "range" else func)
                for name, func in self.SAFE_FUNCTIONS.items()
                if name in self._allowed_functions
            }
        )
        if self._custom_functions:
            safe_globals.update(self._custom_functions)

        i = 0
        while i < len(dep_keys):
            safe_globals[dep_keys[i]] = dep_values[i]
            i += 1

        audit_callback = self._audit_callback
        audit_field_values: Dict[str, Any] = {}
        if audit_callback is not None:
            audit_field_values = {dep_keys[i]: dep_values[i] for i in range(len(dep_keys))}

        try:
            result = eval(code, safe_globals, {})  # noqa: S307
            if audit_callback is not None:
                audit_callback(expression, audit_field_values, result)
        except ScalimComputeExpressionError:
            raise
        except Exception as e:
            expr_id = hashlib.sha256(expression.encode("utf-8")).hexdigest()[:12]
            security_logger.exception("表达式求值失败: expr_hash=%s", expr_id)
            msg = "表达式求值失败 [expr:{}]: {}".format(expr_id, type(e).__name__)
            raise ScalimComputeExpressionError(msg) from e
        else:
            return result


class SecurityAuditLogger:
    def __init__(self, logger_name: str = "scalim.dsl.security") -> None:
        self._logger: logging.Logger = logging.getLogger(logger_name)

    def log_resolve_attempt(self, reference: str, *, success: bool, error: Optional[str] = None) -> None:
        if success:
            self._logger.info(SECURITY_AUDIT_RESOLVED_REFERENCE_LOG, reference)
        else:
            self._logger.warning(SECURITY_AUDIT_FAILED_RESOLVE_LOG, reference, error)

    def log_security_violation(self, reference: str, violation_type: str, details: str) -> None:
        self._logger.error(SECURITY_AUDIT_SECURITY_VIOLATION_LOG, reference, violation_type, details)

    def log_expression_validation(self, expression: str, *, valid: bool, error: Optional[str] = None) -> None:
        if valid:
            self._logger.debug(SECURITY_AUDIT_EXPRESSION_VALID_LOG, expression)
        else:
            self._logger.warning(SECURITY_AUDIT_INVALID_EXPRESSION_LOG, expression, error)


def build_compute_engine() -> "SecureComputeEngine":
    return SecureComputeEngine()


def extract_compute_dependencies(compute_expr: str) -> List[str]:
    return list(extract_dependencies_from_compute(compute_expr, SecureComputeEngine.SAFE_BUILTINS))


__all__ = []
