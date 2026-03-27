import re
from typing import Tuple

from ...exceptions import ScalimYamlException
from ...vendor.dataclassesx import dataclass

_MODULE_PATH_RE = re.compile(r"^[.]*[A-Za-z_][A-Za-z0-9_]*(?:[.][A-Za-z_][A-Za-z0-9_]*)*$")
_REFERENCE_PARTS_COUNT = 2

BUILTIN_CALLABLE_REFERENCE_PREFIX = "^"
_BUILTIN_CALLABLE_ID_RE = re.compile(r"^[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*$")

REFERENCE_FORMAT_EXAMPLES = "`module.path:function` / `module.path:obj.method` / `module.path.function` / `^<id>`"


class ReferenceSyntaxError(ScalimYamlException):
    pass


@dataclass(frozen=True)
class ParsedReference:
    reference: str
    module_path: str
    attr_path: Tuple[str, ...]
    style: str

    @property
    def entry_attr(self) -> str:
        return self.attr_path[0]


def parse_python_reference(reference: str) -> ParsedReference:
    raw = str(reference or "").strip()
    if not raw:
        msg = "引用不能为空"
        raise ReferenceSyntaxError(msg)
    if ":" in raw:
        return _parse_class_style(raw)
    return _parse_dotted_style(raw)


def is_valid_python_reference(reference: str) -> bool:
    try:
        _ = parse_python_reference(reference)
    except ReferenceSyntaxError:
        return False
    return True


def is_valid_builtin_callable_reference(reference: str) -> bool:
    raw = str(reference or "").strip()
    if not raw.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
        return False
    builtin_id = raw[len(BUILTIN_CALLABLE_REFERENCE_PREFIX) :]
    return bool(builtin_id) and _BUILTIN_CALLABLE_ID_RE.fullmatch(builtin_id) is not None


def is_valid_callable_reference(reference: str) -> bool:
    return is_valid_python_reference(reference) or is_valid_builtin_callable_reference(reference)


def _parse_class_style(reference: str) -> ParsedReference:
    parts = reference.split(":")
    if len(parts) != _REFERENCE_PARTS_COUNT:
        msg = "类式引用 '{}' 非法;期望格式: `module.path:attr` 或 `module.path:obj.method`".format(reference)
        raise ReferenceSyntaxError(msg)

    module_path, attr_path = parts
    if module_path and not module_path.strip("."):
        msg = "引用 '{}' 中的相对模块路径 '{}' 非法: 前导点后缺少模块路径".format(reference, module_path)
        raise ReferenceSyntaxError(msg)
    if not module_path or _MODULE_PATH_RE.fullmatch(module_path) is None:
        msg = "引用 '{}' 的模块路径 '{}' 非法".format(reference, module_path)
        raise ReferenceSyntaxError(msg)

    attr_parts = tuple(attr_path.split("."))
    invalid = [part for part in attr_parts if not part or not part.isidentifier()]
    if invalid:
        msg = "引用 '{}' 的属性路径 '{}' 非法".format(reference, attr_path)
        raise ReferenceSyntaxError(msg)

    return ParsedReference(reference=reference, module_path=module_path, attr_path=attr_parts, style="class")


def _parse_dotted_style(reference: str) -> ParsedReference:
    parts = reference.rsplit(".", 1)
    if len(parts) != _REFERENCE_PARTS_COUNT:
        msg = "点号形式引用 '{}' 非法;期望格式: `module.path.function`".format(reference)
        raise ReferenceSyntaxError(msg)

    module_path, func_name = parts
    if not module_path:
        msg = "点号形式引用 '{}' 非法;期望格式: `module.path.function`".format(reference)
        if reference.startswith("."):
            msg = "相对点号引用 '{}' 非法;期望格式: `.module.path.function`".format(reference)
        raise ReferenceSyntaxError(msg)

    if _MODULE_PATH_RE.fullmatch(module_path) is None:
        msg = "引用 '{}' 的模块路径 '{}' 非法".format(reference, module_path)
        raise ReferenceSyntaxError(msg)
    if not func_name.isidentifier():
        msg = "引用 '{}' 的可调用名 '{}' 非法".format(reference, func_name)
        raise ReferenceSyntaxError(msg)

    return ParsedReference(reference=reference, module_path=module_path, attr_path=(func_name,), style="dotted")


__all__ = [
    "BUILTIN_CALLABLE_REFERENCE_PREFIX",
    "REFERENCE_FORMAT_EXAMPLES",
    "ParsedReference",
    "ReferenceSyntaxError",
    "is_valid_builtin_callable_reference",
    "is_valid_callable_reference",
    "is_valid_python_reference",
    "parse_python_reference",
]
