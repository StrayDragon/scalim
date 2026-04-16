# ruff: noqa: T201
"""
检查 `wheel`/`sdist` 的内容边界,避免把非运行时目录打进发行物.

本仓库是多资产工作区(例如:`docs/`、`frontend/`、`notebooks/`、`agentdev/`、`tests/` 等).
对 `PyPI` 发行物,我们希望边界尽量“瘦”:仅包含运行时代码 + 必要资源 + 元数据.

检查项:
- `wheel`: 顶层不应包含 `{tests,docs,notebooks,frontend,artifacts}/`
- `sdist`: 同样检查(会先去掉根目录前缀,例如 `<dist>-<version>/`)

用法:
    `python scripts/check-build-artifacts.py --wheel dist/<dist>-*.whl --sdist dist/<dist>-*.tar.gz`
    `python scripts/check-build-artifacts.py --dist-dir dist`

退出码:
- 0: 通过
- 1: 发现违规 / 入参缺失
"""

from __future__ import annotations

import argparse
import runpy
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, List, Optional, Sequence, Tuple

project_meta = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name("project-meta.py"))))


BANNED_TOPLEVEL_PREFIXES: Tuple[str, ...] = (
    "tests/",
    "docs/",
    "notebooks/",
    "frontend/",
    "agentdev/",
    "artifacts/",
)


def _pick_latest(glob_paths: Sequence[Path]) -> Optional[Path]:
    if not glob_paths:
        return None
    return max(glob_paths, key=lambda p: p.stat().st_mtime)


def _strip_sdist_root(path: str) -> str:
    raw = path.lstrip("/").replace("\\", "/")
    if not raw:
        return ""
    parts = raw.split("/", 1)
    if len(parts) == 1:
        return ""
    return parts[1]


def _iter_wheel_members(wheel_path: Path) -> Iterable[str]:
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            yield str(name)


def _iter_sdist_members(sdist_path: Path) -> Iterable[str]:
    with tarfile.open(sdist_path, mode="r:*") as tf:
        for member in tf.getmembers():
            yield str(member.name)


def _find_violations(paths: Iterable[str], *, strip_root: bool) -> List[str]:
    violations: List[str] = []
    for p in paths:
        rel = _strip_sdist_root(p) if strip_root else p.lstrip("/").replace("\\", "/")
        if not rel:
            continue
        for banned in BANNED_TOPLEVEL_PREFIXES:
            if rel.startswith(banned):
                violations.append(rel)
                break
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 `wheel`/`sdist` 发行物的内容边界.")
    parser.add_argument("--dist-dir", default="dist", help="Directory to locate built artifacts (default: dist).")
    parser.add_argument("--wheel", default="", help="Wheel path (.whl). If empty, pick latest under dist-dir.")
    parser.add_argument("--sdist", default="", help="SDist path (.tar.gz). If empty, pick latest under dist-dir.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    pyproject = project_meta.load_pyproject(repo_root)
    dist_name = str(project_meta.get_path(pyproject, "project.name"))
    dist_dir = (repo_root / str(args.dist_dir)).resolve()

    wheel_glob = "{}-*.whl".format(dist_name)
    sdist_glob = "{}-*.tar.gz".format(dist_name)
    wheel_path = Path(args.wheel).resolve() if args.wheel else _pick_latest(sorted(dist_dir.glob(wheel_glob)))
    sdist_path = Path(args.sdist).resolve() if args.sdist else _pick_latest(sorted(dist_dir.glob(sdist_glob)))

    if wheel_path is None or not wheel_path.exists():
        print("错误: 未找到 `wheel` 发行物. 请先构建: `uv build --wheel --sdist --no-create-gitignore`")
        return 1
    if sdist_path is None or not sdist_path.exists():
        print("错误: 未找到 `sdist` 发行物. 请先构建: `uv build --wheel --sdist --no-create-gitignore`")
        return 1

    wheel_members = list(_iter_wheel_members(wheel_path))
    sdist_members = list(_iter_sdist_members(sdist_path))

    wheel_violations = _find_violations(wheel_members, strip_root=False)
    sdist_violations = _find_violations(sdist_members, strip_root=True)

    if not wheel_violations and not sdist_violations:
        print("OK: 发行物内容边界正常.")
        print("  `wheel`:", wheel_path)
        print("  `sdist`:", sdist_path)
        return 0

    print("错误: 发行物包含非运行时路径.")
    print("  `wheel`:", wheel_path)
    for p in wheel_violations[:200]:
        print("    -", p)
    if len(wheel_violations) > 200:
        print("    ... (还有 {} 条)".format(len(wheel_violations) - 200))

    print("  `sdist`:", sdist_path)
    for p in sdist_violations[:200]:
        print("    -", p)
    if len(sdist_violations) > 200:
        print("    ... (还有 {} 条)".format(len(sdist_violations) - 200))

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
