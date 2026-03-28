import re
from typing import Dict, List, Mapping, Optional, Tuple

from ...._internal.loggingx import format_kv, get_logger, prefix
from ....vendor.compact.typing_extensionsx import TypeGuard
from ....vendor.litejinja2 import TemplateError, from_string

__all__ = [
    "DEFAULT_RENDERED_YAML_MAX_LEN",
    "maybe_precompile_yaml_text",
]

_logger = get_logger("dsl.by_yaml.template_vars")

_TEMPLATE_SANDBOX_SAFE = "safe"
_TEMPLATE_SANDBOX_LEGACY = "legacy"
_TEMPLATE_VARS_JSON_LIKE_SCALARS: Tuple[type, ...] = (bool, int, float, str)
DEFAULT_RENDERED_YAML_MAX_LEN = 1048576


def _is_json_like_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _is_json_like_tuple(value: object) -> TypeGuard[Tuple[object, ...]]:
    return isinstance(value, tuple)


def _is_json_like_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


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


def _validate_json_like_value(value: object, *, path: str) -> None:
    if value is None or isinstance(value, _TEMPLATE_VARS_JSON_LIKE_SCALARS):
        return
    if _is_json_like_list(value) or _is_json_like_tuple(value):
        for idx, item in enumerate(value):
            _validate_json_like_value(item, path="{}[{}]".format(path, idx))
        return
    if _is_json_like_dict(value):
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                _raise_template_vars_not_json_like(
                    path,
                    type_name=type(value).__name__,
                    key_type_name=type(raw_key).__name__,
                )
            _validate_json_like_value(raw_value, path="{}['{}']".format(path, raw_key))
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


def _validate_template_vars_json_like_or_raise(template_vars: Mapping[str, object], *, context_label: str) -> None:
    try:
        _validate_template_vars_json_like(template_vars)
    except ValueError as exc:
        msg = "`YAML` 模板预编译失败: {}: {}".format(str(context_label or ""), exc)
        raise ValueError(msg) from exc


def _validate_rendered_yaml_max_len(rendered_yaml_max_len: int) -> int:
    if isinstance(rendered_yaml_max_len, bool) or not isinstance(rendered_yaml_max_len, int):
        msg = "`rendered_yaml_max_len` must be an integer >= 1"
        raise TypeError(msg)
    max_len = int(rendered_yaml_max_len)
    if max_len < 1:
        msg = "`rendered_yaml_max_len` must be >= 1"
        raise ValueError(msg)
    return max_len


def _ensure_rendered_yaml_within_limit(
    rendered: str,
    *,
    context_label: str,
    context_kind: str,
    max_len: int,
) -> None:
    if len(rendered) <= max_len:
        return
    msg = "渲染后的 YAML 文本超出上限: kind={}, context={}, rendered_len={}, max_len={}".format(
        str(context_kind or ""),
        str(context_label or ""),
        len(rendered),
        int(max_len),
    )
    raise ValueError(msg)


def maybe_precompile_yaml_text(
    text: str,
    *,
    template_vars: Optional[Mapping[str, object]],
    context_label: str,
    context_kind: str,
    template_sandbox: str = _TEMPLATE_SANDBOX_SAFE,
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
) -> str:
    """按需对 `YAML` 文本执行 `LiteJinja2` 预编译.

    约束:
    - 仅当调用方显式提供 `template_vars`(非 `None`)时才启用预编译,以避免误把其它系统的 `{{ ... }}` 当作模板语法.
    - 当前不提供 `tojson`/`toyaml` 等“安全序列化”过滤器;调用方应确保变量渲染结果为合法 `YAML` 文本.
    """
    if template_vars is None:
        return str(text or "")

    sandbox = _validate_template_sandbox(template_sandbox)
    max_len = _validate_rendered_yaml_max_len(rendered_yaml_max_len)

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
        _validate_template_vars_json_like_or_raise(template_vars, context_label=context_label)
        _ensure_rendered_yaml_within_limit(raw, context_label=context_label, context_kind=context_kind, max_len=max_len)
        return raw

    try:
        template = from_string(raw)
        for node in template.nodes:
            if node.get("type") != "var":
                continue
            _scan_template_expr_sandbox_violation(str(node.get("content") or ""), template_sandbox=sandbox)

        _validate_template_vars_json_like_or_raise(template_vars, context_label=context_label)

        rendered = template.render(dict(template_vars), strict_undefined=True, template_sandbox=sandbox)
        _ensure_rendered_yaml_within_limit(rendered, context_label=context_label, context_kind=context_kind, max_len=max_len)
    except TemplateError as exc:
        msg = "`YAML` 模板预编译失败: {}: {}".format(str(context_label or ""), exc)
        raise ValueError(msg) from exc
    else:
        return rendered
