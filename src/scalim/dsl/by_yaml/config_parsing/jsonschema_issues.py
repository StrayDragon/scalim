from typing import Any, Dict, Iterable, List, Tuple, cast

from ....exceptions import ScalimYamlException
from ....vendor.compact.typing_extensionsx import Protocol
from .validators.issues import VALIDATION_SEVERITY_ERROR, ValidationIssue


class JsonSchemaCollectorError(ScalimYamlException):
    pass


class _JsonSchemaValidator(Protocol):
    def iter_errors(self, instance: object) -> Iterable[Any]: ...


class _JsonSchemaDraft7ValidatorFactory(Protocol):
    def __call__(self, schema: Dict[str, Any]) -> _JsonSchemaValidator: ...


def _build_draft7_validator(schema: Dict[str, Any], *, jsonschema_module: Any) -> _JsonSchemaValidator:
    try:
        draft7_validator = jsonschema_module.Draft7Validator
    except AttributeError:
        draft7_validator = None
    if not callable(draft7_validator):
        msg = "jsonschema Draft7Validator unavailable"
        raise JsonSchemaCollectorError(msg)

    validator_factory = cast(
        "_JsonSchemaDraft7ValidatorFactory",
        draft7_validator,
    )  # pragma: allow-cast jsonschema Draft7Validator typed boundary

    try:
        return validator_factory(schema)
    except Exception as exc:
        msg = "jsonschema Draft7Validator init failed: {}: {}".format(type(exc).__name__, exc)
        raise JsonSchemaCollectorError(msg) from exc


def _iter_validation_errors(validator: _JsonSchemaValidator, yaml_data: Dict[str, Any]) -> Iterable[Any]:
    try:
        iter_errors = validator.iter_errors
    except AttributeError:
        iter_errors = None
    if not callable(iter_errors):
        msg = "jsonschema validator missing iter_errors"
        raise JsonSchemaCollectorError(msg)
    return iter_errors(yaml_data)


def _append_context_issues(
    issues: List[ValidationIssue],
    *,
    error: Any,
    filter_additional_properties: bool,
) -> None:
    try:
        context = error.context
    except AttributeError:
        context = None
    if not context:
        return
    for ctx in list(context):
        if filter_additional_properties and _is_additional_properties_error(ctx):
            continue
        issues.append(
            ValidationIssue(
                severity=VALIDATION_SEVERITY_ERROR,
                message="↳ {}".format(_error_message(ctx)),
                path=_format_error_path(ctx),
            )
        )


def _absolute_path(error: Any) -> Tuple[str, ...]:
    try:
        absolute_path = error.absolute_path
    except AttributeError:
        return ()
    if not absolute_path:
        return ()
    try:
        return tuple(str(p) for p in absolute_path)
    except TypeError:
        return (str(absolute_path),)


def _format_error_path(error: Any) -> str:
    path = _absolute_path(error)
    if not path:
        return ""
    return ".".join(path)


def _error_message(error: Any) -> str:
    try:
        msg = error.message
    except AttributeError:
        msg = None
    if isinstance(msg, str) and msg:
        return msg
    return str(error)


def _is_additional_properties_error(error: Any) -> bool:
    try:
        validator = error.validator
    except AttributeError:
        validator = None
    if validator is None:
        return False
    return str(validator) == "additionalProperties"


def _error_sort_key(error: Any) -> Tuple[Tuple[str, ...], str]:
    return _absolute_path(error), _error_message(error)


def collect_jsonschema_validation_issues(
    yaml_data: Dict[str, Any],
    schema: Dict[str, Any],
    *,
    jsonschema_module: Any,
    include_context: bool,
    filter_additional_properties: bool,
) -> List[ValidationIssue]:
    """收集 `JSONSchema` 校验问题, 并保证输出顺序稳定.

    说明:
    - 该 `helper` 刻意保持低层: 不处理可选依赖缺失/异常; 由调用方决定缺失/非预期失败是 `warning` 还是 `error`.
    - `filter_additional_properties=True` 适用于同时启用 `unknown-fields` 检查时过滤 `jsonschema` 的
      `additionalProperties` 报错,避免与自研 `unknown-fields` 诊断重复输出.
    """

    validator = _build_draft7_validator(schema, jsonschema_module=jsonschema_module)
    errors_raw = list(_iter_validation_errors(validator, yaml_data))

    issues: List[ValidationIssue] = []
    for error in sorted(errors_raw, key=_error_sort_key):
        if filter_additional_properties and _is_additional_properties_error(error):
            continue
        issues.append(
            ValidationIssue(
                severity=VALIDATION_SEVERITY_ERROR,
                message="Schema validation error: {}".format(_error_message(error)),
                path=_format_error_path(error),
            )
        )

        if include_context:
            _append_context_issues(
                issues,
                error=error,
                filter_additional_properties=filter_additional_properties,
            )

    return issues


__all__ = [
    "JsonSchemaCollectorError",
    "collect_jsonschema_validation_issues",
]
