import ast
import logging
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import pytest

import scalim.dsl.by_yaml._internal.config_parsing.security as security
from scalim.secure_compute_contracts import is_secure_compute_calculator
from scalim.dsl.by_yaml._internal.config_parsing.security import (
    ScalimComputeExpressionError,
    SecureComputeEngine,
    SecureComputeCalculator,
    SecurityAuditLogger,
    ScalimSecurityError,
    default_audit_callback,
    redacted_audit_callback,
    extract_dependencies_from_compute,
)


def test_compile_caches() -> None:
    engine = SecureComputeEngine()
    calc1 = engine.compile("a + b", ("a", "b"))
    calc2 = engine.compile("a + b", ("a", "b"))
    assert calc1 is calc2


def test_compiled_calculator_supports_positional_and_kwargs() -> None:
    engine = SecureComputeEngine()
    calc = engine.compile("a + b", ("a", "b"))

    assert calc(a=1, b=2) == 3
    assert calc(1, 2) == 3
    assert isinstance(calc, SecureComputeCalculator)
    assert is_secure_compute_calculator(calc)
    assert security.is_secure_compute_calculator(calc)
    assert calc.dependencies == ("a", "b")

    with pytest.raises(TypeError, match="mixed args and kwargs"):
        _ = calc(1, b=2)

    with pytest.raises(TypeError, match="expected 2 positional args"):
        _ = calc(1)


def test_max_compiled_cache_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_compiled_cache_size"):
        _ = SecureComputeEngine(max_compiled_cache_size=0)


def test_compiled_cache_is_bounded_and_evicts_oldest() -> None:
    engine = SecureComputeEngine(max_compiled_cache_size=2)
    _ = engine.compile("a + 1", ("a",))
    _ = engine.compile("b + 1", ("b",))
    _ = engine.compile("c + 1", ("c",))

    assert len(engine._compiled_cache) == 2  # noqa: SLF001
    assert "a + 1:a" not in engine._compiled_cache  # noqa: SLF001


def test_invalid_expression_syntax() -> None:
    engine = SecureComputeEngine()
    with pytest.raises(ScalimComputeExpressionError):
        engine.compile("a +", ("a",))


def test_forbidden_call_patterns() -> None:
    engine = SecureComputeEngine()

    with pytest.raises(ScalimSecurityError):
        engine.compile("max(a=1)", ())

    with pytest.raises(ScalimSecurityError, match="call_by"):
        engine.compile("obj.method()", ("obj",))

    with pytest.raises(ScalimSecurityError):
        engine.compile("a & b", ("a", "b"))

    with pytest.raises(ScalimSecurityError):
        engine.compile("data[0]", ("data",))


def test_method_calls_are_rejected_with_call_by_migration_hint() -> None:
    engine = SecureComputeEngine()

    with pytest.raises(ScalimSecurityError) as excinfo:
        engine.compile("mapping.get('k', None)", ("mapping",))
    assert "method call" in str(excinfo.value).lower() or "method calls" in str(excinfo.value).lower()
    assert "call_by" in str(excinfo.value)

    with pytest.raises(ScalimSecurityError) as excinfo2:
        engine.compile("s.strip()", ("s",))
    assert "method call" in str(excinfo2.value).lower() or "method calls" in str(excinfo2.value).lower()
    assert "call_by" in str(excinfo2.value)


def test_non_name_calls_are_rejected_with_call_by_guidance() -> None:
    engine = SecureComputeEngine()

    with pytest.raises(ScalimSecurityError, match=r"Only simple function calls are allowed.*call_by"):
        engine.compile("(a + b)()", ("a", "b"))


@pytest.mark.parametrize(
    "expression,deps",
    [
        ("{'a': 1}", ()),
        ("{1, 2}", ()),
        ("[x for x in a]", ("a",)),
        ("lambda: 1", ()),
        ('f"{a}"', ("a",)),
        ("a.__class__", ("a",)),
    ],
    ids=["dict", "set", "listcomp", "lambda", "fstring", "attribute"],
)
def test_rejects_unsupported_ast_nodes(expression: str, deps) -> None:  # type: ignore[no-untyped-def]
    engine = SecureComputeEngine()
    with pytest.raises(ScalimSecurityError):
        engine.compile(expression, deps)


def test_compile_supports_bool_list_tuple_and_eval_error() -> None:
    engine = SecureComputeEngine()

    calc_bool = engine.compile("a and b", ("a", "b"))
    assert calc_bool(a=True, b=False) is False

    calc_list = engine.compile("sum([a, b])", ("a", "b"))
    assert calc_list(a=1, b=2) == 3

    calc_tuple = engine.compile("len((a, b))", ("a", "b"))
    assert calc_tuple(a=1, b=2) == 2

    calc_div = engine.compile("a / b", ("a", "b"))
    with pytest.raises(ScalimComputeExpressionError):
        calc_div(a=1, b=0)

    calc_add = engine.compile("a + b", ("a", "b"))
    assert calc_add(a=1, b=2) == 3


def test_secure_compute_supports_decimal_constructor() -> None:
    engine = SecureComputeEngine()
    calc = engine.compile("Decimal('0.1') + Decimal('0.2')", ())
    result = calc()
    assert isinstance(result, Decimal)
    assert result == Decimal("0.3")


def test_secure_compute_supports_dec_helper_and_rejects_invalid_values() -> None:
    engine = SecureComputeEngine()
    calc = engine.compile("dec(value)", ("value",))

    assert calc(value=None) is None
    assert calc(value=True) == Decimal("1")
    assert calc(value=2) == Decimal("2")
    assert calc(value=0.1) == Decimal("0.1")
    assert calc(value=" 1.50 ") == Decimal("1.50")
    assert calc(value=Decimal("2.5")) == Decimal("2.5")

    with pytest.raises(ScalimComputeExpressionError, match="ValueError"):
        calc(value="bad-decimal")

    with pytest.raises(ScalimComputeExpressionError, match="ValueError"):
        calc(value=float("inf"))


def test_allowed_function_map_executes_custom_callable() -> None:
    def double(x: int) -> int:
        return x * 2

    engine = SecureComputeEngine(
        allowed_functions=frozenset({"double"}),
        allowed_function_map={"double": double},
    )
    calc = engine.compile("double(a)", ("a",))
    assert calc(a=3) == 6


def test_allowed_function_map_executes_custom_callable_positional() -> None:
    def double(x: int) -> int:
        return x * 2

    engine = SecureComputeEngine(
        allowed_functions=frozenset({"double"}),
        allowed_function_map={"double": double},
    )
    calc = engine.compile("double(a)", ("a",))
    assert calc(3) == 6


def test_supports_not_unary_operator() -> None:
    engine = SecureComputeEngine()

    calc_not = engine.compile("not a", ("a",))
    assert calc_not(a=True) is False
    assert calc_not(a=False) is True

    calc_neg = engine.compile("-a", ("a",))
    assert calc_neg(a=2) == -2


def test_forbidden_name_rejected() -> None:
    engine = SecureComputeEngine()

    with pytest.raises(ScalimSecurityError):
        engine.compile("__import__", ())


def test_unsupported_comparator_rejected() -> None:
    validator = security.ExpressionValidator(
        allowed_names=set(["a", "b"]),
        allowed_functions=SecureComputeEngine.SAFE_BUILTINS,
        safe_operators=SecureComputeEngine.SAFE_OPERATORS,
        safe_unary=SecureComputeEngine.SAFE_UNARY_OPERATORS,
        safe_comparators={},
        forbidden_names=SecureComputeEngine.FORBIDDEN_NAMES,
    )
    expression = ast.parse("a == b", mode="eval")
    with pytest.raises(ScalimSecurityError):
        validator.validate(expression.body)


def test_validator_accepts_literal_nodes() -> None:
    validator = security.ExpressionValidator(
        allowed_names=set(),
        allowed_functions=SecureComputeEngine.SAFE_BUILTINS,
        safe_operators=SecureComputeEngine.SAFE_OPERATORS,
        safe_unary=SecureComputeEngine.SAFE_UNARY_OPERATORS,
        safe_comparators=SecureComputeEngine.SAFE_COMPARATORS,
        forbidden_names=SecureComputeEngine.FORBIDDEN_NAMES,
    )

    validator.validate(ast.Str("demo"))  # type: ignore[deprecated-class]
    validator.validate(ast.Num(1))  # type: ignore[deprecated-class]


def test_not_in_helper() -> None:
    assert security._not_in([1, 2], 3) is True


def test_extract_dependencies_from_compute_syntax_error() -> None:
    result = extract_dependencies_from_compute("a +", SecureComputeEngine.SAFE_BUILTINS)
    assert result == ()


def test_extract_dependencies_from_compute_excludes_builtins() -> None:
    result = extract_dependencies_from_compute("len(a) + max(b, c)", SecureComputeEngine.SAFE_BUILTINS)
    assert set(result) == {"a", "b", "c"}


def test_extract_dependencies_from_compute_deduplicates() -> None:
    result = extract_dependencies_from_compute("a + a + b", SecureComputeEngine.SAFE_BUILTINS)
    assert result == ("a", "b")


def test_security_audit_logger_emits_messages(caplog) -> None:
    logger = SecurityAuditLogger()

    with caplog.at_level(logging.INFO, logger="scalim.dsl.security"):
        logger.log_resolve_attempt("json.dumps", success=True)
        logger.log_resolve_attempt("bad.ref", success=False, error="boom")
        logger.log_security_violation("bad.ref", "blocked", "unsafe")
        logger.log_expression_validation("a + b", valid=True)
        logger.log_expression_validation("a +", valid=False, error="boom")

    messages = [record.getMessage() for record in caplog.records]
    assert any(security.SECURITY_AUDIT_RESOLVED_REFERENCE_PREFIX in message for message in messages)
    assert any(security.SECURITY_AUDIT_FAILED_RESOLVE_PREFIX in message for message in messages)
    assert any(security.SECURITY_AUDIT_SECURITY_VIOLATION_PREFIX in message for message in messages)


def test_audit_callback_called_on_eval() -> None:
    calls: List[Tuple[str, Dict[str, Any], object]] = []

    def my_audit(expression: str, field_values: Dict[str, Any], result: object) -> None:
        calls.append((expression, field_values.copy(), result))

    engine = SecureComputeEngine(audit_callback=my_audit)
    calc = engine.compile("a + b", ("a", "b"))
    assert calc(a=1, b=2) == 3
    assert calc(1, 2) == 3

    assert len(calls) == 2
    assert calls[0] == ("a + b", {"a": 1, "b": 2}, 3)
    assert calls[1] == ("a + b", {"a": 1, "b": 2}, 3)


def test_positional_eval_error_is_wrapped_as_compute_expression_error() -> None:
    engine = SecureComputeEngine()
    calc = engine.compile("a / b", ("a", "b"))
    with pytest.raises(ScalimComputeExpressionError):
        _ = calc(1, 0)


def test_audit_callback_not_called_when_none() -> None:
    engine = SecureComputeEngine(audit_callback=None)
    calc = engine.compile("a + 1", ("a",))
    result = calc(a=5)
    assert result == 6


def test_default_audit_callback_logs(caplog) -> None:
    engine = SecureComputeEngine(audit_callback=default_audit_callback)
    calc = engine.compile("a * 2", ("a",))

    with caplog.at_level(logging.DEBUG, logger="scalim.dsl.by_yaml.security"):
        calc(a=10)

    assert any(security.EVAL_AUDIT_LOG_PREFIX in record.getMessage() for record in caplog.records)


def test_redacted_audit_callback_logs_only_hash_and_field_names(caplog) -> None:
    engine = SecureComputeEngine(audit_callback=redacted_audit_callback)
    calc = engine.compile("a * 2", ("a",))

    with caplog.at_level(logging.DEBUG, logger="scalim.dsl.by_yaml.security"):
        calc(a=10)

    messages = [record.getMessage() for record in caplog.records]
    assert any("`expr_hash`=" in message for message in messages)
    assert any("`fields`=" in message for message in messages)


def test_compute_limits_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="ComputeLimits.max_expression_len"):
        _ = SecureComputeEngine(limits=security.ComputeLimits(max_expression_len=-1))


def test_compute_limits_rejects_long_expression() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_expression_len=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_expression_len"):
        engine.compile("a + b", ("a", "b"))


def test_compute_limits_rejects_excess_ast_nodes() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_ast_nodes=1))
    with pytest.raises(ScalimComputeExpressionError, match="max_ast_nodes"):
        engine.compile("a", ("a",))


def test_compute_limits_rejects_excess_ast_depth() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_ast_depth=1))
    with pytest.raises(ScalimComputeExpressionError, match="max_ast_depth"):
        engine.compile("a", ("a",))


def test_compute_limits_rejects_literal_string_len() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_literal_string_len=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_literal_string_len"):
        engine.compile("'abcd'", ())


def test_compute_limits_rejects_collection_literal_len() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_collection_literal_len=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_collection_literal_len"):
        engine.compile("sum([1, 2, 3, 4])", ())


def test_compute_limits_rejects_repeat_int_on_left() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_repeat=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_repeat"):
        engine.compile("4 * 'a'", ())


def test_compute_limits_rejects_repeat_int_on_right() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_repeat=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_repeat"):
        engine.compile("'a' * 4", ())


def test_compute_limits_rejects_static_range_len() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_range_len=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_range_len"):
        engine.compile("sum(range(4))", ())


def test_compute_limits_enforces_runtime_range_len() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_range_len=3))
    calc = engine.compile("sum(range(n))", ("n",))
    with pytest.raises(ScalimComputeExpressionError, match="max_range_len"):
        calc(n=4)


def test_compute_limits_enforces_runtime_range_len_positional() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_range_len=3))
    calc = engine.compile("sum(range(n))", ("n",))
    with pytest.raises(ScalimComputeExpressionError, match="max_range_len"):
        _ = calc(4)


def test_compute_limits_runtime_range_len_within_limit_passes() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_range_len=3))
    calc = engine.compile("sum(range(n))", ("n",))
    assert calc(n=3) == 3


def test_compute_limits_repeat_does_not_treat_bool_as_int() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_repeat=0))
    calc = engine.compile("True * 'a'", ())
    assert calc() == "a"


def test_compute_limits_rejects_repeat_list_literal() -> None:
    engine = SecureComputeEngine(limits=security.ComputeLimits(max_repeat=3))
    with pytest.raises(ScalimComputeExpressionError, match="max_repeat"):
        engine.compile("[1] * 4", ())


def test_compute_limits_static_range_len_skips_invalid_range_args() -> None:
    engine = SecureComputeEngine()
    _ = engine.compile("sum(range(1, 10, 0))", ())
