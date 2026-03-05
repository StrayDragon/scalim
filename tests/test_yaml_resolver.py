import pytest

from scalim.dsl.by_yaml.runtime.errors import ResolverError
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver


@pytest.mark.parametrize(
    "ref,match",
    [
        ("no.such.module:func", "Failed to import module"),
        ("json:__name__", "dunder attribute.*forbidden"),
        ("os.path:join.__class__", "dunder attribute.*forbidden"),
        ("json.__name__", "dunder attribute.*forbidden"),
        ("os.path:sep", "is not callable"),
        ("os.path.sep", "is not callable"),
    ],
    ids=[
        "missing-module",
        "dunder-class-style",
        "dunder-class-style-deep",
        "dunder-dotted-style",
        "class-style-not-callable",
        "dotted-style-not-callable",
    ],
)
def test_resolver_rejects_invalid_refs(ref: str, match: str) -> None:
    resolver = PythonReferenceResolver()

    with pytest.raises(ResolverError, match=match):
        resolver.resolve(ref)
