import jsonschema
import pytest

from scalim.dsl.by_yaml._internal.config_parsing import jsonschema_issues as issues_mod


def test_collect_jsonschema_validation_issues_filters_additional_properties_and_sorts() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "main_source": {
                "type": "object",
                "properties": {
                    "loader": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }
    yaml_data = {
        "name": 123,
        "unknown_root": 1,
        "main_source": {"loader": 1, "unknown": 1},
    }

    issues = issues_mod.collect_jsonschema_validation_issues(
        yaml_data,
        schema,
        jsonschema_module=jsonschema,
        include_context=False,
        filter_additional_properties=True,
    )
    assert [issue.path for issue in issues] == ["main_source.loader", "name"]
    assert all("Schema validation error:" in issue.message for issue in issues)


def test_collect_jsonschema_validation_issues_error_cases_and_context_collection() -> None:
    class _DummyError:
        def __init__(self, *, message=None, absolute_path=None, validator=None, context=None) -> None:
            self.message = message
            self.absolute_path = absolute_path or []
            self.validator = validator
            self.context = context

        def __str__(self) -> str:
            return "fallback"

    # 覆盖 `_error_message` 的 fallback 分支
    assert issues_mod._error_message(_DummyError(message=1)) == "fallback"  # noqa: SLF001
    # 覆盖 `_is_additional_properties_error` 在 `validator=None` 的分支
    assert issues_mod._is_additional_properties_error(_DummyError(validator=None)) is False  # noqa: SLF001

    # Draft7Validator 不可用/不可调用
    with pytest.raises(issues_mod.ScalimJsonSchemaCollectorError):  # noqa: SLF001
        _ = issues_mod.collect_jsonschema_validation_issues(
            {},
            {},
            jsonschema_module=object(),
            include_context=False,
            filter_additional_properties=False,
        )

    # Draft7Validator 初始化失败
    class _BadInitJsonSchema:
        class Draft7Validator:
            def __init__(self, _schema: object) -> None:
                raise RuntimeError("boom")

    with pytest.raises(issues_mod.ScalimJsonSchemaCollectorError, match=r"init failed"):  # noqa: SLF001
        _ = issues_mod.collect_jsonschema_validation_issues(
            {},
            {},
            jsonschema_module=_BadInitJsonSchema,
            include_context=False,
            filter_additional_properties=False,
        )

    # validator 缺少 iter_errors
    class _NoIterErrorsJsonSchema:
        class Draft7Validator:
            def __init__(self, _schema: object) -> None:
                self._ = _schema

    with pytest.raises(issues_mod.ScalimJsonSchemaCollectorError, match=r"missing iter_errors"):  # noqa: SLF001
        _ = issues_mod.collect_jsonschema_validation_issues(
            {},
            {},
            jsonschema_module=_NoIterErrorsJsonSchema,
            include_context=False,
            filter_additional_properties=False,
        )

    # include_context=True 且过滤 additionalProperties context
    class _CtxJsonSchema:
        class Draft7Validator:
            def __init__(self, _schema: object) -> None:
                self._ = _schema

            def iter_errors(self, _data: object):
                ctx = [
                    _DummyError(message="ctx ignored", absolute_path=["x"], validator="additionalProperties"),
                    _DummyError(message="ctx kept", absolute_path=["x", "y"], validator="type"),
                ]
                return [
                    _DummyError(message="root", absolute_path=["x"], validator="oneOf", context=ctx),
                ]

    collected = issues_mod.collect_jsonschema_validation_issues(
        {"x": 1},
        {"type": "object"},
        jsonschema_module=_CtxJsonSchema,
        include_context=True,
        filter_additional_properties=True,
    )
    assert [issue.message for issue in collected] == [
        "Schema validation error: root",
        "↳ ctx kept",
    ]

    # 兼容分支: jsonschema error 对象缺少部分常见属性时,仍应给出稳定输出.
    class _AttrLessError:
        def __str__(self) -> str:
            return "fallback"

    class _AttrLessJsonSchema:
        class Draft7Validator:
            def __init__(self, _schema: object) -> None:
                self._ = _schema

            def iter_errors(self, _data: object):
                return [_AttrLessError()]

    collected = issues_mod.collect_jsonschema_validation_issues(
        {"x": 1},
        {"type": "object"},
        jsonschema_module=_AttrLessJsonSchema,
        include_context=True,
        filter_additional_properties=True,
    )
    assert [issue.message for issue in collected] == ["Schema validation error: fallback"]
    assert [issue.path for issue in collected] == [""]


def test_absolute_path_fallback_handles_non_iterable_absolute_path() -> None:
    class _DummyError:
        def __init__(self) -> None:
            self.absolute_path = 123

    err = _DummyError()
    assert issues_mod._absolute_path(err) == ("123",)  # noqa: SLF001
    assert issues_mod._format_error_path(err) == "123"  # noqa: SLF001
