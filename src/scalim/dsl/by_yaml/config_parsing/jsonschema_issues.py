from typing import Any, Dict, Iterable, List, Sequence, Tuple, cast

from .validators.issues import VALIDATION_SEVERITY_ERROR, ValidationIssue


class JsonSchemaCollectorError(RuntimeError):
    pass


def _absolute_path(error: Any) -> Sequence[object]:
    return cast("Sequence[object]", getattr(error, "absolute_path", []) or [])


def _format_error_path(error: Any) -> str:
    path = _absolute_path(error)
    if not path:
        return ""
    return ".".join(str(p) for p in path)


def _error_message(error: Any) -> str:
    msg = getattr(error, "message", None)
    if isinstance(msg, str) and msg:
        return msg
    return str(error)


def _is_additional_properties_error(error: Any) -> bool:
    validator = getattr(error, "validator", None)
    if validator is None:
        return False
    return str(validator) == "additionalProperties"


def _error_sort_key(error: Any) -> Tuple[Tuple[str, ...], str]:
    path = tuple(str(p) for p in _absolute_path(error))
    return path, _error_message(error)


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

    validator_factory = getattr(jsonschema_module, "Draft7Validator", None)
    if not callable(validator_factory):
        msg = "jsonschema Draft7Validator unavailable"
        raise JsonSchemaCollectorError(msg)

    try:
        validator = validator_factory(schema)
    except Exception as exc:
        msg = "jsonschema Draft7Validator init failed: {}: {}".format(type(exc).__name__, exc)
        raise JsonSchemaCollectorError(msg) from exc

    iter_errors = getattr(validator, "iter_errors", None)
    if not callable(iter_errors):
        msg = "jsonschema validator missing iter_errors"
        raise JsonSchemaCollectorError(msg)

    errors_iter = iter_errors(yaml_data)
    errors_raw = list(cast("Iterable[Any]", errors_iter))

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
            context = getattr(error, "context", None)
            if context:
                for ctx in cast("Iterable[Any]", context):
                    if filter_additional_properties and _is_additional_properties_error(ctx):
                        continue
                    issues.append(
                        ValidationIssue(
                            severity=VALIDATION_SEVERITY_ERROR,
                            message="↳ {}".format(_error_message(ctx)),
                            path=_format_error_path(ctx),
                        )
                    )

    return issues


__all__ = [
    "JsonSchemaCollectorError",
    "collect_jsonschema_validation_issues",
]
