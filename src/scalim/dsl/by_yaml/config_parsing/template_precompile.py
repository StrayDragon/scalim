import re
from typing import Dict, Mapping, Optional, Sequence, Tuple, cast

from ...._internal.loggingx import format_kv, get_logger, prefix
from ....vendor.litejinja2 import TemplateError, from_string

__all__ = [
    "maybe_precompile_yaml_text",
]

_logger = get_logger("dsl.by_yaml.template_vars")

_TEMPLATE_SANDBOX_SAFE = "safe"
_TEMPLATE_SANDBOX_LEGACY = "legacy"
_TEMPLATE_VARS_JSON_LIKE_SCALARS: Tuple[type, ...] = (bool, int, float, str)


def _validate_template_sandbox(template_sandbox: str) -> str:
    value = str(template_sandbox or "").strip() or _TEMPLATE_SANDBOX_SAFE
    if value not in {_TEMPLATE_SANDBOX_SAFE, _TEMPLATE_SANDBOX_LEGACY}:
        msg = "`template_sandbox` 必须是以下值之一: `safe`, `legacy`"
        raise ValueError(msg)
    return value


_VAR_EXPR_METHOD_CALL_RE = re.compile(r"\.[A-Za-z_][A-Za-z0-9_]*\(\)")
_VAR_EXPR_UNDERSCORE_PART_RE = re.compile(r"(^|\.)_")


def _scan_template_expr_sandbox_violation(var_expr: str, *, template_sandbox: str) -> None:
    raw = str(var_expr or "").strip()
    base_expr = raw.split("|", 1)[0].strip()

    if _VAR_EXPR_UNDERSCORE_PART_RE.search(base_expr):
        msg = "`template_sandbox` 禁止访问以下划线开头属性"
        raise TemplateError(msg)
    if template_sandbox == _TEMPLATE_SANDBOX_SAFE and _VAR_EXPR_METHOD_CALL_RE.search(base_expr):
        msg = "`template_sandbox=safe` 禁止无参方法调用"
        raise TemplateError(msg)


def _raise_template_vars_not_json_like(
    path: str,
    *,
    type_name: str,
    key_type_name: Optional[str] = None,
) -> None:
    msg = "`template_vars` 必须是 `JSON/YAML-like` 类型: 路径=`{}`, 类型=`{}`".format(path, type_name)
    if key_type_name is not None:
        msg = msg + ", 键类型={}".format(key_type_name)
    raise ValueError(msg)


def _validate_json_like_sequence(seq: Sequence[object], *, path: str) -> None:
    for idx, item in enumerate(seq):
        _validate_json_like_value(item, path="{}[{}]".format(path, idx))


def _validate_json_like_dict(mapping: Dict[object, object], *, path: str) -> None:
    for k, v in mapping.items():
        if not isinstance(k, str):
            _raise_template_vars_not_json_like(path, type_name=type(mapping).__name__, key_type_name=type(k).__name__)
        key_str = cast("str", k)
        _validate_json_like_value(v, path="{}['{}']".format(path, key_str))


def _validate_json_like_value(value: object, *, path: str) -> None:
    if value is None or isinstance(value, _TEMPLATE_VARS_JSON_LIKE_SCALARS):
        return
    if isinstance(value, (list, tuple)):
        _validate_json_like_sequence(cast("Sequence[object]", value), path=path)
        return
    if isinstance(value, dict):
        _validate_json_like_dict(cast("Dict[object, object]", value), path=path)
        return
    _raise_template_vars_not_json_like(path, type_name=type(value).__name__)


def _validate_template_vars_json_like(template_vars: Mapping[str, object]) -> None:
    for key, value in template_vars.items():
        if not isinstance(key, str):
            _raise_template_vars_not_json_like(
                "template_vars",
                type_name=type(template_vars).__name__,
                key_type_name=type(key).__name__,
            )
        _validate_json_like_value(value, path="template_vars['{}']".format(key))


def maybe_precompile_yaml_text(
    text: str,
    *,
    template_vars: Optional[Mapping[str, object]],
    context_label: str,
    template_sandbox: str = _TEMPLATE_SANDBOX_SAFE,
) -> str:
    """按需对 `YAML` 文本执行 `LiteJinja2` 预编译.

    约束:
    - 仅当调用方显式提供 `template_vars`(非 `None`)时才启用预编译,以避免误把其它系统的 `{{ ... }}` 当作模板语法.
    - 当前不提供 `tojson`/`toyaml` 等“安全序列化”过滤器;调用方应确保变量渲染结果为合法 `YAML` 文本.
    """
    if template_vars is None:
        return str(text or "")

    sandbox = _validate_template_sandbox(template_sandbox)
    if sandbox == _TEMPLATE_SANDBOX_LEGACY:
        _logger.warning(
            "%s启用 `template_sandbox=legacy`(不安全): %s",
            prefix("template_vars"),
            format_kv(
                template_sandbox=sandbox,
                context_label=str(context_label or ""),
                template_vars_keys=len(template_vars),
            ),
        )

    # 轻量优化: 无模板标记时跳过渲染(不影响语义).
    raw = str(text or "")
    if "{{" not in raw and "{%" not in raw:
        try:
            _validate_template_vars_json_like(template_vars)
        except ValueError as exc:
            msg = "`YAML` 模板预编译失败: {}: {}".format(str(context_label or ""), exc)
            raise ValueError(msg) from exc
        return raw

    try:
        template = from_string(raw)
        for node in template.nodes:
            if node.get("type") != "var":
                continue
            _scan_template_expr_sandbox_violation(str(node.get("content") or ""), template_sandbox=sandbox)

        try:
            _validate_template_vars_json_like(template_vars)
        except ValueError as exc:
            msg = "`YAML` 模板预编译失败: {}: {}".format(str(context_label or ""), exc)
            raise ValueError(msg) from exc

        return template.render(dict(template_vars), strict_undefined=True, template_sandbox=sandbox)
    except TemplateError as exc:
        msg = "`YAML` 模板预编译失败: {}: {}".format(str(context_label or ""), exc)
        raise ValueError(msg) from exc
