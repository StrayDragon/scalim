from typing import Iterator

import pytest

from scalim.vendor.litejinja2 import Environment, Template, TemplateError, clear_cache, from_string


def test_litejinja2_renders_vars_and_filters() -> None:
    clear_cache()
    tpl = from_string("Hello {{ name | upper }}, n={{ items | length }}, d={{ missing | default('x') }}, t={{ s | trim | lower }}")
    out = tpl.render({"name": "World", "items": [1, 2, 3], "s": "  A  "})
    assert out == "Hello WORLD, n=3, d=x, t=a"


def test_litejinja2_if_else_and_defined_ops() -> None:
    tpl = from_string("{% if user is defined and not disabled %}ok{% else %}no{% endif %}")
    assert tpl.render({"user": "u", "disabled": ""}) == "ok"
    assert tpl.render({"disabled": ""}) == "no"

    tpl = from_string("{% if user is not defined or not user %}no{% else %}yes{% endif %}")
    assert tpl.render({"user": ""}) == "no"
    assert tpl.render({"user": "u"}) == "yes"

    tpl = from_string("{% if a %}A{% if b %}B{% endif %}{% endif %}")
    assert tpl.render({"a": "x", "b": "y"}) == "AB"


def test_litejinja2_for_loop_unpack_and_loop_ctx() -> None:
    tpl = from_string("{% for x, y in items %}{{ loop.index0 }}={{ x }}-{{ y }};{% endfor %}")
    out = tpl.render({"items": [(1, 2), (3,), 4]})
    assert out == "0=1-2;1=3-;2=-;"

    tpl = from_string("{% for k in mapping %}{{ k }}{% endfor %}")
    assert tpl.render({"mapping": {"a": 1, "b": 2}}) in ("ab", "ba")


def test_litejinja2_set_and_expression_eval() -> None:
    tpl = from_string('{% set x = "pre_" + name | upper %}{{ x }}')
    assert tpl.render({"name": "ok"}) == "pre_OK"

    tpl = from_string("{% set n = 123 %}{{ n }}")
    assert tpl.render({}) == "123"

    tpl = from_string('{% set s = prefix + name + "_suf" %}{{ s }}')
    assert tpl.render({"prefix": "p_", "name": "n"}) == "p_n_suf"


def test_litejinja2_variable_access_dict_list_attr_and_method() -> None:
    class User:
        def __init__(self, name: str) -> None:
            self.name = name

        def get_name(self) -> str:
            return self.name

    tpl = from_string('{{ user.name }}|{{ user.get_name() }}|{{ config["k"] }}|{{ config[key] }}|{{ items[idx] }}|{{ items[idx_missing] }}')
    out = tpl.render({"user": User("Ada"), "config": {"k": "v"}, "key": "k", "items": [10, 20], "idx": 1, "idx_missing": 99})
    assert out == "Ada|Ada|v|v|20|"


def test_litejinja2_errors_raise_template_error() -> None:
    tpl = from_string("{% for x items %}{{ x }}{% endfor %}")
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"items": [1]})
    assert "无效的 `for` 循环语法" in str(exc_info.value)

    tpl = from_string("{% for x in items %}{{ x }}{% endfor %}")
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"items": 123})
    assert "不可迭代" in str(exc_info.value)

    class BadIter:
        def __iter__(self) -> Iterator[object]:
            raise TypeError("bad")

    tpl = from_string("{% for x in items %}{{ x }}{% endfor %}")
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"items": BadIter()})
    assert "无法转换为列表" in str(exc_info.value)

    tpl = from_string("{% for x in items %}{{ x }}")
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"items": [1]})
    assert "未找到对应的 `endfor`" in str(exc_info.value)

    tpl = from_string("{% if a %}x")
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"a": True})
    assert "未找到对应的 `endif`" in str(exc_info.value)

    tpl = from_string("{{ name | no_such_filter }}")
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"name": "x"})
    assert "未知的过滤器" in str(exc_info.value)

    def explode(value: object) -> object:
        raise ValueError("boom")

    tpl = Template("{{ x | explode }}", filters={"explode": explode})
    with pytest.raises(TemplateError) as exc_info:
        _ = tpl.render({"x": "x"})
    assert "过滤器" in str(exc_info.value)


def test_litejinja2_environment_caching_and_clear_cache() -> None:
    env = Environment()
    t1 = env.from_string("{{ a }}")
    t2 = env.from_string("{{ a }}")
    assert t1 is t2

    env.clear_cache()
    t3 = env.from_string("{{ a }}")
    assert t3 is not t1
