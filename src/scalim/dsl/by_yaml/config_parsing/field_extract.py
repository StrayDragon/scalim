from typing import List, Optional, Tuple, Union

ExtractSegment = Union[str, int]


class FieldExtractCompileError(ValueError):
    pass


def compile_field_extract(expr: str) -> Tuple[ExtractSegment, ...]:
    """
    将 `dot + bracket` 路径表达式编译为一串带类型的段.

    支持的段:
    - 点路径标识符: `a.b.c`
    - 中括号整型键: `[1]`
    - 中括号字符串键: `["a.b"]` / `['a.b']` (支持最小转义: `\\` / `\"` / `\'`)

    注意:
    - 不做 `"1"` ↔ `1` 的隐式转换
    - 不支持 `list`/`tuple` 下标语义: `[1]` 永远表示 键=1
    """
    if not isinstance(expr, str) or not expr:
        msg = "extract must be a non-empty string"
        raise FieldExtractCompileError(msg)

    i = 0
    n = len(expr)
    segments: List[ExtractSegment] = []

    while i < n:
        if expr[i] == ".":
            msg = "extract contains empty segment at position {}".format(i)
            raise FieldExtractCompileError(msg)

        segment, i = _parse_segment(expr, i)
        segments.append(segment)

        if i >= n:
            break
        if expr[i] == ".":
            i += 1
            if i >= n:
                msg = "extract must not end with '.'"
                raise FieldExtractCompileError(msg)
            continue
        if expr[i] == "[":
            continue

        msg = "extract has invalid character '{}' at position {}".format(expr[i], i)
        raise FieldExtractCompileError(msg)

    return tuple(segments)


def derive_source_field_data_key(*, field_id: str, extract: Optional[str]) -> str:
    """
    解析源字段的扁平 `data_key`(用于 `output.fields` 选择器与 `relation.steps` 引用等旧语义).

    规则:
    - 未声明 `extract` -> `data_key = field_id`
    - `extract` 编译后恰好只有一个字符串段 -> `data_key = 该段`
    - 其它情况 -> `data_key = field_id`
    """
    expr = field_id if extract is None else str(extract)
    try:
        segments = compile_field_extract(expr)
    except FieldExtractCompileError:
        return field_id
    if len(segments) == 1 and isinstance(segments[0], str):
        return segments[0]
    return field_id


def _parse_segment(expr: str, i: int) -> Tuple[ExtractSegment, int]:
    if expr[i] == "[":
        return _parse_bracket_segment(expr, i)
    return _parse_identifier(expr, i)


def _parse_identifier(expr: str, i: int) -> Tuple[str, int]:
    n = len(expr)
    if i >= n:
        msg = "extract contains empty identifier segment"
        raise FieldExtractCompileError(msg)

    ch0 = expr[i]
    if not _is_ident_start(ch0):
        msg = ("extract has invalid identifier start '{}' at position {}; use bracket string segment for special keys").format(ch0, i)
        raise FieldExtractCompileError(msg)
    j = i + 1
    while j < n and _is_ident_char(expr[j]):
        j += 1
    return expr[i:j], j


def _parse_bracket_segment(expr: str, i: int) -> Tuple[ExtractSegment, int]:
    n = len(expr)
    if (
        i >= n or expr[i] != "["
    ):  # pragma: no cover  # pragma: allow-no-cover internal invariant: caller only dispatches to bracket parser on '['
        msg = "internal error: expected '['"
        raise FieldExtractCompileError(
            msg
        )  # pragma: no cover  # pragma: allow-no-cover internal invariant: caller only dispatches to bracket parser on '['
    if i + 1 >= n:
        msg = "extract has unclosed bracket at position {}".format(i)
        raise FieldExtractCompileError(msg)

    ch = expr[i + 1]
    if "0" <= ch <= "9":
        return _parse_bracket_int(expr, i + 1)
    if ch in {'"', "'"}:
        return _parse_bracket_string(expr, i + 2, quote=ch)

    msg = ("extract has invalid bracket segment at position {}; int key must be [0-9]+, string key must be [\"...\"] or ['...']").format(i)
    raise FieldExtractCompileError(msg)


def _parse_bracket_int(expr: str, i: int) -> Tuple[int, int]:
    n = len(expr)
    start = i
    j = i
    while j < n and ("0" <= expr[j] <= "9"):
        j += 1
    if j == start:
        msg = "extract has empty int bracket segment"
        raise FieldExtractCompileError(
            msg
        )  # pragma: no cover  # pragma: allow-no-cover internal invariant: digit branch only enters when first char is [0-9]
    if j >= n or expr[j] != "]":
        msg = "extract has invalid int bracket segment at position {}; use '[1]' (no spaces, no sign)".format(start - 1)
        raise FieldExtractCompileError(msg)
    value = int(expr[start:j])
    return value, j + 1


def _parse_bracket_string(expr: str, i: int, *, quote: str) -> Tuple[str, int]:
    n = len(expr)
    chars: List[str] = []
    j = i
    found_quote = False
    while j < n:
        ch = expr[j]
        if ch == quote:
            j += 1
            found_quote = True
            break
        if ch == "\\":
            if j + 1 >= n:
                msg = "extract has unclosed escape sequence at position {}".format(j)
                raise FieldExtractCompileError(msg)
            next_ch = expr[j + 1]
            if next_ch == "\\":
                chars.append("\\")
                j += 2
                continue
            if next_ch == quote:
                chars.append(quote)
                j += 2
                continue
            msg = "extract has invalid escape sequence '\\{}' at position {}".format(next_ch, j)
            raise FieldExtractCompileError(msg)
        chars.append(ch)
        j += 1

    if not found_quote:
        msg = "extract has unclosed quoted string in bracket segment"
        raise FieldExtractCompileError(msg)
    if j >= n or expr[j] != "]":
        msg = "extract bracket string segment must end with ']'"
        raise FieldExtractCompileError(msg)
    return "".join(chars), j + 1


def _is_ident_start(ch: str) -> bool:
    return ch == "_" or ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def _is_ident_char(ch: str) -> bool:
    return _is_ident_start(ch) or ("0" <= ch <= "9")


__all__ = [
    "ExtractSegment",
    "FieldExtractCompileError",
    "compile_field_extract",
    "derive_source_field_data_key",
]
