from typing import Tuple

_SAFE = "safe"
_LEGACY = "legacy"
_KNOWN: Tuple[str, ...] = (_SAFE,)


def validate_public_template_sandbox(template_sandbox: str) -> str:
    """校验 YAML DSL 官方公开入口允许的 `template_sandbox`.

    - 官方公开入口仅允许 `safe`
    - `legacy` 模式已移除,系统不再支持
    """
    value = str(template_sandbox or "").strip() or _SAFE

    if value == _SAFE:
        return _SAFE
    if value == _LEGACY:
        msg = (
            "`template_sandbox='legacy'` 已移除;当前仅支持 `safe`. 迁移: 删除 `template_sandbox` 参数或显式设置 `template_sandbox='safe'`."
        )
        raise ValueError(msg)
    msg = "`template_sandbox` 必须是 `safe`(YAML DSL 官方公开入口); 收到={!r}; 已知值={}".format(value, ", ".join(_KNOWN))
    raise ValueError(msg)


__all__ = ()
