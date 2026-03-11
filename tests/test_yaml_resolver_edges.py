import logging
import math

import pytest

from scalim.dsl.by_yaml.runtime.errors import ResolverError
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver, SecurePythonReferenceResolver
from scalim.dsl.by_yaml.runtime.references import (
    ALLOWLIST_WILDCARD_FUNCTIONS_WARNING,
    ALLOWLIST_WILDCARD_MODULES_WARNING,
)


def test_resolver_rejects_invalid_dotted_reference() -> None:
    resolver = PythonReferenceResolver()

    with pytest.raises(ResolverError, match="点号形式引用 .* 非法"):
        resolver.resolve("invalid")


def test_resolver_rejects_invalid_dotted_callable_name() -> None:
    resolver = PythonReferenceResolver()

    with pytest.raises(ResolverError, match="可调用名 '1bad' 非法"):
        resolver.resolve("math.1bad")


def test_resolver_max_cache_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_cache_size"):
        _ = PythonReferenceResolver(max_cache_size=0)


def test_resolver_rejects_disallowed_module_and_function() -> None:
    cases = [
        (PythonReferenceResolver(allowed_modules=frozenset(["allowed"])), "math.sqrt", "allowed_modules"),
        (PythonReferenceResolver(allowed_functions=frozenset(["math:sqrt"])), "math.pow", "allowed_functions"),
    ]
    for resolver, ref, match in cases:
        with pytest.raises(ResolverError, match=match):
            resolver.resolve(ref)


def test_resolver_allows_explicit_function_over_module_allowlist() -> None:
    resolver = PythonReferenceResolver(
        allowed_modules=frozenset(["allowed"]),
        allowed_functions=frozenset(["math:sqrt"]),
    )

    resolved = resolver.resolve("math.sqrt")
    assert resolved is math.sqrt


def test_resolver_allows_wildcard_modules_and_warns(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="scalim.dsl.by_yaml.runtime")
    resolver = PythonReferenceResolver(allowed_modules=frozenset(["*"]))

    resolved = resolver.resolve("math.sqrt")
    assert resolved is math.sqrt
    assert any(ALLOWLIST_WILDCARD_MODULES_WARNING in record.getMessage() for record in caplog.records)


def test_resolver_allows_wildcard_functions_and_warns(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="scalim.dsl.by_yaml.runtime")
    caplog.clear()
    resolver = PythonReferenceResolver(allowed_functions=frozenset(["*"]))

    resolved = resolver.resolve("math.sqrt")
    assert resolved is math.sqrt
    assert any(ALLOWLIST_WILDCARD_FUNCTIONS_WARNING in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "ref,match",
    [
        ("missing.module.fn", "导入模块 'missing.module' 失败"),
        ("math.missing", "模块 'math' 不存在属性 'missing'"),
    ],
    ids=["missing-module", "missing-attr"],
)
def test_resolver_import_and_attribute_errors(ref: str, match: str) -> None:
    resolver = PythonReferenceResolver()

    with pytest.raises(ResolverError, match=match):
        resolver.resolve(ref)


@pytest.mark.parametrize(
    "ref,match",
    [
        ("os.path:join", "危险模块列表"),
        ("math.__class__", "危险模式 '__'"),
    ],
    ids=["dangerous-module", "dangerous-pattern"],
)
def test_secure_resolver_blocks_dangerous_reference(ref: str, match: str) -> None:
    resolver = SecurePythonReferenceResolver()

    with pytest.raises(ResolverError, match=match):
        resolver.resolve(ref)


@pytest.mark.parametrize(
    "allowed_fn",
    [
        "tests.resolver_allowlist_mod:Obj.safe",
        "tests.resolver_allowlist_mod.Obj.safe",
    ],
    ids=["class-style", "dotted"],
)
def test_resolver_class_style_allowlist_matches_full_attr_chain(allowed_fn: str) -> None:
    resolver = PythonReferenceResolver(allowed_functions=frozenset([allowed_fn]))

    safe = resolver.resolve("tests.resolver_allowlist_mod:Obj.safe")
    assert safe() == "safe"

    with pytest.raises(ResolverError, match="Obj.unsafe"):
        resolver.resolve("tests.resolver_allowlist_mod:Obj.unsafe")


def test_resolver_allowed_modules_allows_class_style_methods() -> None:
    resolver = PythonReferenceResolver(allowed_modules=frozenset(["tests.resolver_allowlist_mod"]))

    safe = resolver.resolve("tests.resolver_allowlist_mod:Obj.safe")
    unsafe = resolver.resolve("tests.resolver_allowlist_mod:Obj.unsafe")

    assert safe() == "safe"
    assert unsafe() == "unsafe"


def test_resolver_cache_is_bounded_and_clear_cache_works() -> None:
    resolver = PythonReferenceResolver(max_cache_size=2)
    _ = resolver.resolve("math.sqrt")
    _ = resolver.resolve("math.pow")
    _ = resolver.resolve("math.floor")

    assert len(resolver._cache) == 2  # noqa: SLF001
    assert "math.sqrt" not in resolver._cache  # noqa: SLF001

    resolver.clear_cache()
    assert not resolver._cache  # noqa: SLF001
