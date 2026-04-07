from typing import Tuple

_SAFE = "safe"
_LEGACY = "legacy"
_KNOWN: Tuple[str, ...] = (_SAFE, _LEGACY)


def validate_public_template_sandbox(template_sandbox: str) -> str:
    """校验 YAML DSL 官方公开入口允许的 `template_sandbox`.

    - 官方公开入口仅允许 `safe`
    - `legacy` 属于不安全行为,必须转入显式 `unsafe` 语义的非公共入口
    """
    value = str(template_sandbox or "").strip() or _SAFE

    if value == _SAFE:
        return _SAFE
    if value == _LEGACY:
        msg = (
            "`template_sandbox='legacy'` 已不再被 YAML DSL 官方公开入口支持(仅允许 `safe`). "
            "迁移: 删除 `template_sandbox` 参数或显式设置 `template_sandbox='safe'`. "
            "如确需 legacy 行为,必须改用显式 `unsafe` 语义的非公共入口."
        )
        raise ValueError(msg)
    msg = "`template_sandbox` 必须是 `safe`(YAML DSL 官方公开入口); 收到={!r}; 已知值={}".format(value, ", ".join(_KNOWN))
    raise ValueError(msg)


__all__ = ()
