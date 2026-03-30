import pytest

from scalim.dsl.by_yaml.runtime.errors import ScalimResolverError
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver


@pytest.mark.parametrize(
    "ref,match",
    [
        ("no.such.module:func", "导入模块"),
        ("json:__name__", "禁止访问双下划线属性"),
        ("os.path:join.__class__", "禁止访问双下划线属性"),
        ("json.__name__", "禁止访问双下划线属性"),
        ("os.path:sep", "不是可调用对象"),
        ("os.path.sep", "不是可调用对象"),
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

    with pytest.raises(ScalimResolverError, match=match):
        resolver.resolve(ref)
