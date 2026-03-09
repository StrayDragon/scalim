# ruff: noqa: T201
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_toml(text: str) -> Dict[str, Any]:
    try:
        import tomllib  # py311+

        return tomllib.loads(text)  # type: ignore[no-any-return]
    except ModuleNotFoundError:
        pass

    try:
        import tomli

        return tomli.loads(text)  # type: ignore[no-any-return]
    except ModuleNotFoundError:
        pass

    try:
        import tomlkit

        return _to_builtin(tomlkit.parse(text))  # type: ignore[no-any-return]
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少 `TOML` 解析器. 请安装 `tomli`(推荐)或 `tomlkit`.") from exc


def load_pyproject(root: Path | None = None) -> Dict[str, Any]:
    root = root or repo_root()
    path = root / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    return _load_toml(text)


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return [_to_builtin(v) for v in value]
    return value


def get_path(data: Dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    parts = [p for p in dotted.split(".") if p]
    for idx, part in enumerate(parts):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError("缺少键: {} (当前类型={})".format(".".join(parts[: idx + 1]), type(cur).__name__))
        cur = cur[part]
    return cur


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")


def _print_value(value: Any) -> None:
    if isinstance(value, (dict, list, tuple)):
        _print_json(value)
        return
    sys.stdout.write(str(value))
    sys.stdout.write("\n")


def _usage() -> None:
    cmds: List[str] = [
        "python scripts/project-meta.py json",
        "python scripts/project-meta.py get project.name",
        "python scripts/project-meta.py get tool.scalim.viz.dir_name",
    ]
    sys.stderr.write("用法:\n  {}\n".format("\n  ".join(cmds)))


def main(argv: Iterable[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv:
        _usage()
        return 2

    cmd = argv[0].strip()
    pyproject = load_pyproject()

    if cmd == "json":
        _print_json(pyproject)
        return 0

    if cmd == "get":
        if len(argv) != 2:
            _usage()
            return 2
        key = argv[1].strip()
        try:
            value = get_path(pyproject, key)
        except KeyError as exc:
            sys.stderr.write("错误: {}\n".format(str(exc)))
            return 1
        _print_value(value)
        return 0

    _usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
