from typing import Mapping, Optional

from ....vendor.litejinja2 import TemplateError, from_string

__all__ = [
    "maybe_precompile_yaml_text",
]


def maybe_precompile_yaml_text(
    text: str,
    *,
    template_vars: Optional[Mapping[str, object]],
    context_label: str,
) -> str:
    """按需对 `YAML` 文本执行 `LiteJinja2` 预编译.

    约束:
    - 仅当调用方显式提供 `template_vars`(非 `None`)时才启用预编译,以避免误把其它系统的 `{{ ... }}` 当作模板语法.
    - 当前不提供 `tojson`/`toyaml` 等“安全序列化”过滤器;调用方应确保变量渲染结果为合法 `YAML` 文本.
    """
    if template_vars is None:
        return str(text or "")

    # 轻量优化: 无模板标记时跳过渲染(不影响语义).
    raw = str(text or "")
    if "{{" not in raw and "{%" not in raw:
        return raw

    try:
        template = from_string(raw)
        return template.render(dict(template_vars), strict_undefined=True)
    except TemplateError as exc:
        msg = "`YAML` 模板预编译失败: {}: {}".format(str(context_label or ""), exc)
        raise ValueError(msg) from exc
