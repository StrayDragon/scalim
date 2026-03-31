#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
# ruff: noqa: T201
"""`TOON` 工具：`JSON` ⇄ `TOON` 编解码。

用法：
  - `JSON` → `TOON`：
      `uv run scripts/tool-toon.py encode --input data.json --output data.toon`
      `cat data.json | uv run scripts/tool-toon.py encode > data.toon`

  - `TOON` → `JSON`：
      `uv run scripts/tool-toon.py decode --input data.toon --output data.json`
      `cat data.toon | uv run scripts/tool-toon.py decode > data.json`
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence


def _read_text(path: Optional[Path]) -> str:
    if not path:
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def _write_text(path: Optional[Path], text: str) -> None:
    if not path:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_delimiter(value: str) -> str:
    if value == "comma":
        return ","
    if value == "tab":
        return "\t"
    if value == "pipe":
        return "|"
    raise ValueError("未知分隔符: `{}`".format(value))


_NUMBER_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$")


def _escape_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t").replace('"', '\\"')


def _unescape_string(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        if i + 1 >= len(value):
            out.append("\\")
            i += 1
            continue

        nxt = value[i + 1]
        if nxt == "n":
            out.append("\n")
            i += 2
            continue
        if nxt == "r":
            out.append("\r")
            i += 2
            continue
        if nxt == "t":
            out.append("\t")
            i += 2
            continue
        if nxt == "\\":
            out.append("\\")
            i += 2
            continue
        if nxt == '"':
            out.append('"')
            i += 2
            continue

        out.append(nxt)
        i += 2
    return "".join(out)


def _needs_quotes(value: str, *, delimiter: str) -> bool:
    if value == "":
        return True
    if value != value.strip():
        return True
    if delimiter in value:
        return True
    if "\n" in value or "\r" in value or "\t" in value:
        return True
    if '"' in value:
        return True
    if ":" in value:
        return True
    if value in ("null", "true", "false"):
        return True
    if _NUMBER_RE.match(value):
        return True
    return False


def _encode_scalar(value: Any, *, delimiter: str) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    if isinstance(value, str):
        if _needs_quotes(value, delimiter=delimiter):
            return '"' + _escape_string(value) + '"'
        return value
    raise TypeError("不支持的标量类型: {}".format(type(value).__name__))


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _encode_table_rows(
    items: Sequence[dict[str, Any]],
    *,
    columns: Sequence[str],
    indent: int,
    level: int,
    delimiter: str,
) -> list[str]:
    lines: list[str] = []
    prefix = " " * (indent * (level + 1))
    for item in items:
        row_cells: list[str] = []
        for col in columns:
            row_cells.append(_encode_scalar(item.get(col), delimiter=delimiter))
        lines.append(prefix + delimiter.join(row_cells))
    return lines


def _encode_mapping(
    mapping: dict[str, Any],
    *,
    indent: int,
    level: int,
    delimiter: str,
    length_marker: bool,
) -> list[str]:
    lines: list[str] = []
    prefix = " " * (indent * level)

    for key, value in mapping.items():
        if isinstance(value, dict):
            if not value:
                lines.append("{}{}: {{}}".format(prefix, key))
                continue
            lines.append("{}{}:".format(prefix, key))
            lines.extend(_encode_mapping(value, indent=indent, level=level + 1, delimiter=delimiter, length_marker=length_marker))
            continue

        if isinstance(value, list):
            marker = "#" if length_marker else ""
            meta = "[{}{}{}]".format(marker, len(value), delimiter)

            if not value:
                lines.append("{}{}{}:".format(prefix, key, meta))
                continue

            if all(_is_scalar(item) for item in value):
                rendered = delimiter.join(_encode_scalar(item, delimiter=delimiter) for item in value)
                lines.append("{}{}{}: {}".format(prefix, key, meta, rendered))
                continue

            if all(isinstance(item, dict) for item in value):
                items = [dict(item) for item in value]  # type: ignore[arg-type]
                first_keys = list(items[0].keys())
                first_key_set = set(first_keys)
                if all(set(item.keys()) == first_key_set and all(_is_scalar(item.get(col)) for col in first_keys) for item in items):
                    header = delimiter.join(first_keys)
                    lines.append("{}{}{}{{{}}}:".format(prefix, key, meta, header))
                    lines.extend(_encode_table_rows(items, columns=first_keys, indent=indent, level=level, delimiter=delimiter))
                    continue

            raise TypeError("不支持的列表结构(仅支持标量列表或同构 `dict` 表格): `{}`".format(key))

        if _is_scalar(value):
            lines.append("{}{}: {}".format(prefix, key, _encode_scalar(value, delimiter=delimiter)))
            continue

        raise TypeError("不支持的值类型: {} -> {}".format(key, type(value).__name__))

    return lines


def _split_delimited(text: str, *, delimiter: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_quotes = False
    escaping = False
    for ch in text:
        if escaping:
            buf.append(ch)
            escaping = False
            continue
        if in_quotes and ch == "\\":
            buf.append(ch)
            escaping = True
            continue
        if ch == '"':
            buf.append(ch)
            in_quotes = not in_quotes
            continue
        if not in_quotes and ch == delimiter:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return parts


def _decode_scalar(text: str) -> Any:
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return _unescape_string(text[1:-1])

    if text == "null":
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if _NUMBER_RE.match(text):
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    return text


def _decode_mapping(lines: Sequence[str], *, start: int, indent: int, base_indent: int) -> tuple[dict[str, Any], int]:
    out: dict[str, Any] = {}
    i = start
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        curr_indent = len(raw) - len(raw.lstrip(" "))
        if curr_indent < base_indent:
            break
        if curr_indent != base_indent:
            raise ValueError("无效缩进: {}: `{}`".format(i + 1, raw))

        content = raw[base_indent:]
        key_part, sep, rest = content.partition(":")
        if sep != ":":
            raise ValueError("无法解析行(缺少 `:`): {}: `{}`".format(i + 1, raw))

        rest = rest.lstrip(" ")
        key_part = key_part.rstrip()

        key, list_meta = _parse_key_meta(key_part)
        if list_meta:
            length = list_meta["length"]
            delimiter = list_meta["delimiter"]
            columns = list_meta.get("columns")
            if columns:
                # 表格列表
                items: list[dict[str, Any]] = []
                i += 1
                if length == 0:
                    out[key] = items
                    continue

                row_indent = None
                for _ in range(length):
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    if i >= len(lines):
                        raise ValueError("表格行不足: `{}`".format(key))
                    row_raw = lines[i]
                    curr = len(row_raw) - len(row_raw.lstrip(" "))
                    if row_indent is None:
                        if curr <= base_indent:
                            raise ValueError("表格缩进错误: `{}`".format(key))
                        row_indent = curr
                    if curr != row_indent:
                        raise ValueError("表格行缩进不一致: `{}`".format(key))
                    row_text = row_raw[row_indent:]
                    cells = _split_delimited(row_text, delimiter=delimiter)
                    if len(cells) != len(columns):
                        raise ValueError("表格列数不匹配: `{}`".format(key))
                    row_item: dict[str, Any] = {}
                    for col, cell in zip(columns, cells):
                        row_item[col] = _decode_scalar(cell)
                    items.append(row_item)
                    i += 1
                out[key] = items
                continue

            # 行内列表
            if not rest:
                out[key] = []
                i += 1
                continue
            parts = _split_delimited(rest, delimiter=delimiter)
            out[key] = [_decode_scalar(part) for part in parts if part != ""]
            i += 1
            continue

        if rest:
            if rest == "{}":
                out[key] = {}
                i += 1
                continue
            out[key] = _decode_scalar(rest)
            i += 1
            continue

        # 嵌套映射
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            out[key] = {}
            break
        next_raw = lines[i]
        next_indent = len(next_raw) - len(next_raw.lstrip(" "))
        if next_indent <= base_indent:
            out[key] = {}
            continue
        nested, new_i = _decode_mapping(lines, start=i, indent=indent, base_indent=next_indent)
        out[key] = nested
        i = new_i
    return out, i


def _parse_key_meta(key_part: str) -> tuple[str, Optional[dict[str, Any]]]:
    if "[" not in key_part:
        return key_part, None

    base, rest = key_part.split("[", 1)
    inside, after = rest.split("]", 1)
    marker = ""
    if inside.startswith("#"):
        marker = "#"
        inside = inside[1:]
    if not inside:
        raise ValueError("缺少列表长度: `{}`".format(key_part))

    delimiter = inside[-1]
    length_str = inside[:-1]
    try:
        length = int(length_str)
    except ValueError as exc:
        raise ValueError("无效列表长度: `{}`".format(key_part)) from exc

    columns: Optional[list[str]] = None
    after = after.strip()
    if after:
        if not (after.startswith("{") and after.endswith("}")):
            raise ValueError("无效表格头: `{}`".format(key_part))
        header = after[1:-1]
        columns = _split_delimited(header, delimiter=delimiter)

    return base, {"length": length, "delimiter": delimiter, "columns": columns, "length_marker": marker}


def _cmd_encode(*, input_path: Optional[Path], output_path: Optional[Path], indent: int, delimiter: str, length_marker: bool) -> int:
    data = json.loads(_read_text(input_path))
    delim = _parse_delimiter(delimiter)

    if isinstance(data, dict):
        lines = _encode_mapping(data, indent=indent, level=0, delimiter=delim, length_marker=bool(length_marker))
        rendered = "\n".join(lines)
    elif isinstance(data, list):
        marker = "#" if length_marker else ""
        meta = "[{}{}{}]".format(marker, len(data), delim)
        if not data:
            rendered = "{}:".format(meta)
        elif all(_is_scalar(item) for item in data):
            rendered = "{}: {}".format(meta, delim.join(_encode_scalar(item, delimiter=delim) for item in data))
        else:
            raise TypeError("`TOON` 顶层仅支持 `dict` 或标量列表。")
    elif _is_scalar(data):
        rendered = _encode_scalar(data, delimiter=delim)
    else:
        raise TypeError("`TOON` 顶层仅支持 `dict` / `list` / 标量。")
    if not rendered.endswith("\n"):
        rendered += "\n"
    _write_text(output_path, rendered)
    return 0


def _cmd_decode(*, input_path: Optional[Path], output_path: Optional[Path], pretty: bool) -> int:
    text = _read_text(input_path)
    lines = [line.rstrip("\n") for line in text.splitlines()]
    data, i = _decode_mapping(lines, start=0, indent=2, base_indent=0)
    if i < len(lines):
        trailing = "\n".join(lines[i:]).strip()
        if trailing:
            raise ValueError("存在无法解析的尾部内容。")
    if pretty:
        rendered = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    else:
        rendered = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"
    _write_text(output_path, rendered)
    return 0


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JSON <-> TOON 编解码工具。")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encode", help="JSON -> TOON")
    p_enc.add_argument("--input", type=Path, help="输入 JSON 文件(默认: stdin)")
    p_enc.add_argument("--output", type=Path, help="输出 TOON 文件(默认: stdout)")
    p_enc.add_argument("--indent", type=int, default=2, help="缩进空格数(默认: 2)")
    p_enc.add_argument("--delimiter", choices=["comma", "tab", "pipe"], default="tab", help="数组 delimiter(默认: tab)")
    p_enc.add_argument("--length-marker", action="store_true", help="在数组长度前增加 marker(#)")

    p_dec = sub.add_parser("decode", help="TOON -> JSON")
    p_dec.add_argument("--input", type=Path, help="输入 TOON 文件(默认: stdin)")
    p_dec.add_argument("--output", type=Path, help="输出 JSON 文件(默认: stdout)")
    p_dec.add_argument("--pretty", action="store_true", help="pretty JSON 输出")

    return p.parse_args(list(argv or sys.argv[1:]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    if args.cmd == "encode":
        return _cmd_encode(
            input_path=args.input,
            output_path=args.output,
            indent=args.indent,
            delimiter=args.delimiter,
            length_marker=bool(args.length_marker),
        )
    if args.cmd == "decode":
        return _cmd_decode(
            input_path=args.input,
            output_path=args.output,
            pretty=bool(args.pretty),
        )
    raise AssertionError("不应到达的分支: `{}`".format(args.cmd))


if __name__ == "__main__":
    raise SystemExit(main())
