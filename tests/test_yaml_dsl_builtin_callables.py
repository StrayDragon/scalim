import pytest

from scalim.dsl.by_yaml.config_parsing.call_by import parse_call_by
from scalim.dsl.by_yaml.reference_syntax import is_valid_callable_reference
from scalim.dsl.by_yaml.runtime.builtin_callables import is_builtin_callable_reference, list_builtin_callable_ids, parse_builtin_callable_id
from scalim.dsl.by_yaml.runtime.compiler import create_reference_resolver
from scalim.dsl.by_yaml.runtime.errors import ScalimResolverError
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver
from scalim.workflow.loaders import book_sheet_rows
from tests.call_by_fns import echo


def test_is_valid_callable_reference_accepts_builtin_prefix() -> None:
    assert is_valid_callable_reference("^workflow/book_sheet_rows") is True
    assert is_valid_callable_reference("^") is False
    assert is_valid_callable_reference("^bad-id") is False


def test_is_builtin_callable_reference_smoke() -> None:
    assert is_builtin_callable_reference("^workflow/book_sheet_rows") is True
    assert is_builtin_callable_reference("tests.call_by_fns:echo") is False


def test_list_builtin_callable_ids_smoke() -> None:
    assert "workflow/book_sheet_rows" in list_builtin_callable_ids()


def test_parse_call_by_accepts_builtin_reference() -> None:
    parsed = parse_call_by("^workflow/book_sheet_rows(ref)")
    assert parsed.reference == "^workflow/book_sheet_rows"
    assert parsed.field_names == ("ref",)


def test_parse_builtin_callable_id_errors() -> None:
    with pytest.raises(ScalimResolverError, match="Not a builtin callable reference"):
        parse_builtin_callable_id("tests.call_by_fns:echo")
    with pytest.raises(ScalimResolverError, match="missing <id>"):
        parse_builtin_callable_id("^")
    with pytest.raises(ScalimResolverError, match="Invalid builtin callable id"):
        parse_builtin_callable_id("^bad-id")


def test_resolver_resolves_builtin_scheme_without_allowlist_for_scalim() -> None:
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"]))
    fn = resolver.resolve("^workflow/book_sheet_rows")
    assert fn is book_sheet_rows


def test_resolver_builtin_cache_eviction_smoke() -> None:
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"]), max_cache_size=1)
    _ = resolver.resolve("^workflow/book_sheet_rows")
    _ = resolver.resolve("^workflow/book_sheet_rows ")


def test_resolver_unknown_builtin_id_fails_fast() -> None:
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"]))
    with pytest.raises(ScalimResolverError, match=r"Unknown builtin callable id"):
        resolver.resolve("^unknown/id")


def test_create_reference_resolver_accepts_custom_builtin_callables_as_callables() -> None:
    resolver = create_reference_resolver(
        allowed_modules=frozenset(["tests.call_by_fns"]),
        allowed_functions=None,
        builtin_callables={"custom/echo": echo},
        public_builtin_callable_ids=("custom/echo",),
    )
    assert resolver.resolve("^custom/echo") is echo


def test_create_reference_resolver_accepts_custom_builtin_callables_as_python_references() -> None:
    resolver = create_reference_resolver(
        allowed_modules=frozenset(["tests.call_by_fns"]),
        allowed_functions=None,
        builtin_callables={"custom/echo": "tests.call_by_fns:echo"},
    )
    assert resolver.resolve("^custom/echo") is echo


def test_create_reference_resolver_rejects_invalid_custom_builtin_callables_vocab() -> None:
    with pytest.raises(ValueError, match=r"builtin_callables: <id> must not be empty"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"": echo},
        )

    with pytest.raises(ValueError, match=r"must not include prefix"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"^custom/echo": echo},
        )

    with pytest.raises(ValueError, match=r"invalid <id>"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"bad-id": echo},
        )


def test_create_reference_resolver_rejects_invalid_custom_builtin_callables_vocab_value() -> None:
    with pytest.raises(ValueError, match=r"value must not be empty"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"custom/echo": "  "},
        )

    with pytest.raises(ValueError, match=r"value must be a Python reference"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"custom/echo": "^workflow/book_sheet_rows"},
        )

    with pytest.raises(ValueError, match=r"failed to resolve Python reference"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"custom/echo": "bad-ref"},
        )

    with pytest.raises(TypeError, match=r"expected a callable or Python reference string"):
        _ = create_reference_resolver(
            allowed_modules=frozenset(["tests.call_by_fns"]),
            allowed_functions=None,
            builtin_callables={"custom/echo": 123},
        )
