# pragma: allow-c901-file plan: c60

import ast
from dataclasses import dataclass
from typing import Any

from .....exceptions import ScalimYamlError
from ...reference_syntax import REFERENCE_FORMAT_EXAMPLES, is_valid_callable_reference

_CTX_TOKEN = "$ctx"  # noqa: S105
_CTX_PLACEHOLDER = "__scalim_ctx__"
_CALL_PLACEHOLDER = "__scalim_call__"

ALLOWED_CTX_ATTRS: tuple[str, ...] = (
    "row_id",
    "batch_num",
    "field_id",
    "deps",
    "values",
)

_NON_PY_LITERAL_NAMES: frozenset[str] = frozenset(["true", "false", "null"])


class ScalimCallByParseError(ScalimYamlError):
    pass


@dataclass(frozen=True)
class CallByValue:
    kind: str
    value: Any


@dataclass(frozen=True)
class ParsedCallBy:
    reference: str
    args: tuple[CallByValue, ...]
    kwargs: tuple[tuple[str, CallByValue], ...]
    field_names: tuple[str, ...]


def parse_call_by(call_by: Any) -> ParsedCallBy:
    raw = _normalize_call_by(call_by)
    reference, node = _parse_call_by_call(raw)
    args, kwargs, field_names = _parse_call_by_call_args(node)
    return ParsedCallBy(reference=reference, args=args, kwargs=kwargs, field_names=field_names)


def _normalize_call_by(call_by: Any) -> str:
    if not isinstance(call_by, str):
        msg = "call_by must be a string"
        raise ScalimCallByParseError(msg)
    raw = call_by.strip()
    if not raw:
        msg = "call_by must not be empty"
        raise ScalimCallByParseError(msg)
    return raw


def _parse_call_by_call(raw: str) -> tuple[str, ast.Call]:
    reference, args_src = _split_reference_and_args(raw)
    if not _is_valid_loader_ref(reference):
        msg = f"`call_by` 引用 '{reference}' 非法. 期望格式: {REFERENCE_FORMAT_EXAMPLES}"
        raise ScalimCallByParseError(msg)

    rewritten_args = _rewrite_ctx_tokens(args_src)
    call_src = f"{_CALL_PLACEHOLDER}(\n{rewritten_args}\n)"

    try:
        tree = ast.parse(call_src, mode="eval")
    except SyntaxError as e:
        msg = f"Invalid call_by arguments syntax: {e}"
        raise ScalimCallByParseError(msg) from e

    node = tree.body
    if not isinstance(
        node, ast.Call
    ):  # pragma: no cover  # pragma: allow-no-cover ast.parse(eval) with placeholder call should always yield ast.Call
        msg = "Invalid call_by syntax: expected a function call"
        raise ScalimCallByParseError(msg)
    if (
        not isinstance(node.func, ast.Name) or node.func.id != _CALL_PLACEHOLDER
    ):  # pragma: no cover  # pragma: allow-no-cover ast.parse(eval) placeholder call should always use ast.Name
        msg = "Invalid call_by syntax: expected a simple function call"
        raise ScalimCallByParseError(msg)

    return reference, node


def _parse_call_by_call_args(node: ast.Call) -> tuple[tuple[CallByValue, ...], tuple[tuple[str, CallByValue], ...], tuple[str, ...]]:
    args: list[CallByValue] = []
    kwargs: list[tuple[str, CallByValue]] = []
    deps: list[str] = []
    seen: set[str] = set()
    kw_names: set[str] = set()

    for arg in node.args:
        if isinstance(arg, ast.Starred):
            msg = "call_by does not allow '*' argument unpacking"
            raise ScalimCallByParseError(msg)
        parsed = _parse_value(arg)
        args.append(parsed)
        _collect_dep(parsed, deps, seen)

    for kw in node.keywords:
        if kw.arg is None:
            msg = "call_by does not allow '**' keyword unpacking"
            raise ScalimCallByParseError(msg)
        if kw.arg in kw_names:
            msg = f"call_by has duplicate keyword argument '{kw.arg}'"
            raise ScalimCallByParseError(msg)
        kw_names.add(kw.arg)
        parsed = _parse_value(kw.value)
        kwargs.append((kw.arg, parsed))
        _collect_dep(parsed, deps, seen)

    return tuple(args), tuple(kwargs), tuple(deps)


def _collect_dep(value: CallByValue, deps: list[str], seen: set[str]) -> None:
    if value.kind != "field":
        return
    name = str(value.value)
    if name in seen:
        return
    seen.add(name)
    deps.append(name)


def extract_call_by_dependencies(call_by: str) -> list[str]:
    try:
        parsed = parse_call_by(call_by)
    except ScalimCallByParseError:
        return []
    return list(parsed.field_names)


def _split_reference_and_args(raw: str) -> tuple[str, str]:
    open_idx = raw.find("(")
    if open_idx < 0:
        msg = "Invalid call_by syntax: expected '<reference>(...)'"
        raise ScalimCallByParseError(msg)
    reference = raw[:open_idx].strip()
    if not reference:
        msg = "Invalid call_by syntax: missing reference before '('"
        raise ScalimCallByParseError(msg)

    close_idx = _find_matching_paren(raw, open_idx)
    if close_idx is None:
        msg = "Invalid call_by syntax: missing closing ')'"
        raise ScalimCallByParseError(msg)
    if not _is_only_whitespace_or_comment(raw[close_idx + 1 :]):
        msg = "Invalid call_by syntax: unexpected trailing content after ')'"
        raise ScalimCallByParseError(msg)

    args_src = raw[open_idx + 1 : close_idx].strip()
    return reference, args_src


def _find_matching_paren(text: str, open_idx: int) -> int | None:
    depth = 0
    in_str = False
    quote = ""
    escaped = False

    i = open_idx
    while i < len(text):
        ch = text[i]
        if in_str:
            in_str, quote, escaped = _advance_in_str(ch, quote, escaped=escaped)
            i += 1
            continue

        if ch in ("'", '"'):
            in_str = True
            quote = ch
            i += 1
            continue

        if ch == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return None


def _is_only_whitespace_or_comment(text: str) -> bool:
    stripped = str(text or "").lstrip()
    if not stripped:
        return True
    return stripped.startswith("#")


def _rewrite_ctx_tokens(src: str) -> str:
    if not src:
        return ""

    if _has_placeholder_token(src):
        msg = f"Illegal token '{_CTX_PLACEHOLDER}' in call_by arguments; use '$ctx' instead"
        raise ScalimCallByParseError(msg)

    out: list[str] = []
    i = 0
    in_str = False
    quote = ""
    escaped = False

    while i < len(src):
        ch = src[i]
        if in_str:
            out.append(ch)
            in_str, quote, escaped = _advance_in_str(ch, quote, escaped=escaped)
            i += 1
            continue

        if ch in ("'", '"'):
            in_str = True
            quote = ch
            out.append(ch)
            i += 1
            continue

        if ch == "#":
            while i < len(src) and src[i] != "\n":
                out.append(src[i])
                i += 1
            continue

        if src.startswith(_CTX_TOKEN, i):
            j = i + len(_CTX_TOKEN)
            if j == len(src) or src[j] in (".", ",", ")", "=", " ", "\t", "\r", "\n"):
                out.append(_CTX_PLACEHOLDER)
                i = j
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def _has_placeholder_token(src: str) -> bool:
    i = 0
    in_str = False
    quote = ""
    escaped = False

    while i < len(src):
        ch = src[i]
        if in_str:
            in_str, quote, escaped = _advance_in_str(ch, quote, escaped=escaped)
            i += 1
            continue

        if ch in ("'", '"'):
            in_str = True
            quote = ch
            i += 1
            continue

        if ch == "#":
            while i < len(src) and src[i] != "\n":
                i += 1
            continue

        if src.startswith(_CTX_PLACEHOLDER, i):
            return True
        i += 1

    return False


def _advance_in_str(ch: str, quote: str, *, escaped: bool) -> tuple[bool, str, bool]:
    if escaped:
        return True, quote, False
    if ch == "\\":
        return True, quote, True
    if ch == quote:
        return False, "", False
    return True, quote, False


def _parse_value(node: ast.AST) -> CallByValue:
    if isinstance(node, ast.Name):
        name = node.id
        if name == _CTX_PLACEHOLDER:
            return CallByValue(kind="ctx", value=None)
        if name in _NON_PY_LITERAL_NAMES:
            msg = f"Invalid literal '{name}': use True/False/None"
            raise ScalimCallByParseError(msg)
        return CallByValue(kind="field", value=name)

    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == _CTX_PLACEHOLDER:
            attr = node.attr
            if attr not in ALLOWED_CTX_ATTRS:
                msg = "Invalid ctx attribute '{}'. Allowed: {}".format(attr, ", ".join(ALLOWED_CTX_ATTRS))
                raise ScalimCallByParseError(msg)
            return CallByValue(kind="ctx_attr", value=attr)
        msg = "Only '$ctx' or '$ctx.<attr>' is allowed for attribute access"
        raise ScalimCallByParseError(msg)

    literal = _parse_literal(node)
    if literal is not _MISSING:
        return CallByValue(kind="literal", value=literal)

    msg = f"Unsupported call_by argument type: {type(node).__name__}"
    raise ScalimCallByParseError(msg)


_MISSING = object()


def _parse_literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, (int, float, str, bool)) or value is None:
            return value
        msg = f"Unsupported literal type in call_by: {type(value).__name__}"
        raise ScalimCallByParseError(msg)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _parse_literal(node.operand)
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            msg = "Unary +/- in call_by only supports numeric literals"
            raise ScalimCallByParseError(msg)
        return operand if isinstance(node.op, ast.UAdd) else -operand

    if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
        msg = "Only simple Python literals are allowed in call_by (int/float/str/True/False/None)"
        raise ScalimCallByParseError(msg)

    return _MISSING


def _is_valid_loader_ref(loader_ref: str) -> bool:
    return is_valid_callable_reference(loader_ref)


__all__ = ()
