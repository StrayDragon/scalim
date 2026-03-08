#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "tomli>=2.0.0; python_version < '3.11'",
# ]
# ///
# ruff: noqa: T201
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


def _load_toml(text: str) -> Any:
    try:
        import tomllib  # py311+

        return tomllib.loads(text)
    except ModuleNotFoundError:
        import tomli

        return tomli.loads(text)


def _read_toml(path: Path) -> Any:
    return _load_toml(path.read_text(encoding="utf-8"))


def _get_path(data: Any, key_path: str) -> Any:
    current = data
    parts = [part for part in key_path.split(".") if part]
    if not parts:
        return current

    for idx, part in enumerate(parts):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError("缺少键: {}".format(".".join(parts[: idx + 1])))
            current = current[part]
            continue
        if isinstance(current, (list, tuple)):
            try:
                nth = int(part)
            except ValueError as exc:
                raise KeyError("路径段 '{}' 不是合法下标: {}".format(part, ".".join(parts[:idx]))) from exc
            try:
                current = current[nth]
            except IndexError as exc:
                raise KeyError("列表下标越界: {}".format(".".join(parts[: idx + 1]))) from exc
            continue
        raise KeyError(
            "路径 '{}' 在 '{}' 处不可继续访问(当前类型={})".format(
                key_path,
                ".".join(parts[:idx]),
                type(current).__name__,
            )
        )
    return current


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    return value


def _format_value(value: Any, output_format: str) -> str:
    builtins_value = _to_builtin(value)

    if output_format == "json":
        return json.dumps(builtins_value, ensure_ascii=False)

    if output_format == "value":
        if isinstance(builtins_value, (dict, list)):
            return json.dumps(builtins_value, ensure_ascii=False)
        return str(builtins_value)

    if output_format == "lines":
        if not isinstance(builtins_value, list):
            raise TypeError("`--format lines` 仅支持列表值")
        return "\n".join(str(item) for item in builtins_value)

    if output_format == "shell-words":
        if isinstance(builtins_value, list):
            return " ".join(shlex.quote(str(item)) for item in builtins_value)
        return shlex.quote(str(builtins_value))

    raise ValueError("未知输出格式: {}".format(output_format))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="读取任意 TOML 文件中的 key 路径值")
    parser.add_argument("--file", default="pyproject.toml", help="TOML 文件路径，默认 `pyproject.toml`")
    parser.add_argument("--key", required=True, help="点分 key 路径，例如 `tool.basedpyright.strict`")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("json", "value", "lines", "shell-words"),
        default="json",
        help="输出格式，默认 `json`",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    toml_path = Path(args.file)
    try:
        data = _read_toml(toml_path)
        value = _get_path(data, args.key)
        print(_format_value(value, args.output_format))
    except Exception as exc:  # noqa: BLE001
        print("错误: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
