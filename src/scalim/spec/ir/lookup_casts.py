from typing import Optional

from ...vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class LookupCastSpecIr:
    """关联键转换规范(纯数据,不包含可调用对象)."""

    name: str = "auto"
    sep: Optional[str] = None


def lookup_cast_id(spec: "LookupCastSpecIr", *, is_multi: bool) -> str:
    """为关联键转换规范生成稳定的标识符字符串.

    用途:
    - 作为 `RuntimeBindings.lookup_key_casts` 的键,用于查找已解析的转换函数;
    - 作为快照输出的一部分,保证排序与去重稳定.
    """

    name = str(spec.name or "").strip() or "auto"
    sep = spec.sep
    scope = "multi" if bool(is_multi) else "single"
    if name == "sep_first":
        return "lookup_cast:{}:{}:sep={!r}".format(scope, name, sep or ",")
    return "lookup_cast:{}:{}".format(scope, name)


__all__ = (
    "LookupCastSpecIr",
    "lookup_cast_id",
)
