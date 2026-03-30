# ruff: noqa: T201
from __future__ import annotations

import argparse
import re
import runpy
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Sequence, Tuple

project_meta = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name("project-meta.py"))))


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
_TOML_VERSION_RE = re.compile(r'(?m)^(version\s*=\s*")([^"]+)(")\s*$')
_JSON_VERSION_RE = re.compile(r'(?m)^(\s*"version"\s*:\s*")([^"]+)("\s*,\s*)$')


@dataclass(frozen=True)
class _Target:
    relpath: str
    kind: str


_TARGETS: Tuple[_Target, ...] = (
    _Target("pyproject.toml", "toml"),
    _Target("packages/scalim-benchlib/pyproject.toml", "toml"),
    _Target("packages/scalim-misc/pyproject.toml", "toml"),
    _Target("frontend/scalim-viz/package.json", "json"),
)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统一主包/子包/前端版本号(白名单文件,默认 dry-run).")
    parser.add_argument("--version", help="目标版本号.为空则跟随根 `pyproject.toml` 当前版本.")
    parser.add_argument("--apply", action="store_true", help="实际写入文件.默认仅预览.")
    parser.add_argument("--root", default=str(project_meta.repo_root()), help="仓库根目录(默认: 当前仓库).")
    return parser.parse_args(list(argv or sys.argv[1:]))


def _validate_version(version: str) -> str:
    normalized = version.strip()
    if not _VERSION_RE.fullmatch(normalized):
        raise ValueError("无效版本: {!r}。期望类似 `0.2.1` 的语义化版本".format(version))
    return normalized


def _read_current_root_version(root: Path) -> str:
    pyproject = project_meta.load_pyproject(root)
    version = project_meta.get_path(pyproject, "project.version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("`project.version` 必须是非空字符串")
    return version.strip()


def _replace_version(text: str, *, version: str, kind: str, relpath: str) -> Tuple[str, str]:
    regex = _TOML_VERSION_RE if kind == "toml" else _JSON_VERSION_RE
    match = regex.search(text)
    if match is None:
        raise ValueError("未在 {} 中找到版本字段".format(relpath))
    current = match.group(2)
    updated = text[: match.start()] + match.group(1) + version + match.group(3) + text[match.end() :]
    return updated, current


def _iter_planned_changes(root: Path, target_version: str) -> List[Tuple[Path, str, str]]:
    plans: List[Tuple[Path, str, str]] = []
    for target in _TARGETS:
        path = root / target.relpath
        if not path.exists():
            raise FileNotFoundError("目标文件不存在: {}".format(path))
        text = path.read_text(encoding="utf-8")
        updated, current = _replace_version(text, version=target_version, kind=target.kind, relpath=target.relpath)
        if updated != text:
            plans.append((path, current, target_version))
    return plans


def _apply_changes(root: Path, target_version: str) -> List[Path]:
    changed_paths: List[Path] = []
    pyproject_changed = False
    for target in _TARGETS:
        path = root / target.relpath
        text = path.read_text(encoding="utf-8")
        updated, _current = _replace_version(text, version=target_version, kind=target.kind, relpath=target.relpath)
        if updated == text:
            continue
        path.write_text(updated, encoding="utf-8")
        changed_paths.append(path)
        if target.relpath == "pyproject.toml":
            pyproject_changed = True

    generator = root / "scripts" / "gen-project-constants.py"
    if pyproject_changed and generator.exists():
        subprocess.run([sys.executable, str(generator)], cwd=str(root), check=True)

    return changed_paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print("仓库根目录不存在: {}".format(root), file=sys.stderr)
        return 2

    try:
        current_root_version = _read_current_root_version(root)
        target_version = _validate_version(args.version or current_root_version)
        plans = _iter_planned_changes(root, target_version)
    except Exception as exc:
        print("错误: {}".format(exc), file=sys.stderr)
        return 2

    print("根目录:", root)
    print("target_version:", target_version)
    print("模式:", "`apply`" if args.apply else "`dry-run`")
    print("")

    if not plans:
        print("版本已经对齐。")
        return 0

    print("计划变更:")
    for path, current, target in plans:
        print("- {}: {} -> {}".format(path.relative_to(root), current, target))

    if not args.apply:
        print("")
        print("当前仅执行 `dry-run`。如需写入，请使用 `--apply` 重新运行。")
        return 0

    changed_paths = _apply_changes(root, target_version)
    print("")
    print("已更新文件:")
    for path in changed_paths:
        print("- {}".format(path.relative_to(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
