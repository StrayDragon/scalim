#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "toon-format",
# ]
#
# [tool.uv.sources]
# toon-format = { git = "https://github.com/toon-format/toon-python.git" }
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


def _cmd_encode(*, input_path: Optional[Path], output_path: Optional[Path], indent: int, delimiter: str, length_marker: bool) -> int:
    from toon_format import encode
    from toon_format.types import EncodeOptions

    data = json.loads(_read_text(input_path))
    opts = EncodeOptions(indent=indent, delimiter=_parse_delimiter(delimiter), lengthMarker="#" if length_marker else False)
    rendered = encode(data, opts)
    if not rendered.endswith("\n"):
        rendered += "\n"
    _write_text(output_path, rendered)
    return 0


def _cmd_decode(*, input_path: Optional[Path], output_path: Optional[Path], pretty: bool) -> int:
    from toon_format import decode

    data = decode(_read_text(input_path))
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
