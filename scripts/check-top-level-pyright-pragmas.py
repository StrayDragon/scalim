#!/usr/bin/env python3
# NOTE: 继续按模块簇清理下一批顶层` # pyright: #`

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Set

DEFAULT_HEAD_LINES = 5
DEFAULT_MANIFEST = "scripts/top-level-pyright-pragmas.txt"


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 `src/scalim/` 顶层 `# pyright:` pragma 清单是否同步")
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help="允许清单文件路径，默认 `scripts/top-level-pyright-pragmas.txt`",
    )
    parser.add_argument(
        "--head-lines",
        type=int,
        default=DEFAULT_HEAD_LINES,
        help="扫描文件前几行以识别顶层 `# pyright:`，默认 5",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="用当前源码扫描结果覆盖清单文件",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _scan_top_level_pyright_files(repo_root: Path, *, head_lines: int) -> Set[str]:
    src_root = repo_root / "src" / "scalim"
    found: Set[str] = set()

    for path in src_root.rglob("*.py"):
        head = path.read_text(encoding="utf-8").splitlines()[: max(1, head_lines)]
        if any(line.startswith("# pyright:") for line in head):
            found.add(path.relative_to(repo_root).as_posix())
    return found


def _load_manifest(path: Path) -> Set[str]:
    if not path.exists():
        raise FileNotFoundError("清单文件不存在: {}".format(path.as_posix()))

    items: Set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        items.add(line)
    return items


def _write_manifest(path: Path, items: Iterable[str]) -> None:
    lines: List[str] = [
        "# 当前允许保留顶层 `# pyright:` pragma 的文件清单",
        "# 由 `python scripts/check-top-level-pyright-pragmas.py --sync` 同步生成",
        "",
    ]
    lines.extend(sorted(items))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / args.manifest

    found = _scan_top_level_pyright_files(repo_root, head_lines=args.head_lines)

    if args.sync:
        _write_manifest(manifest_path, found)
        print("已同步顶层 `# pyright:` 清单: {} ({} 项)".format(args.manifest, len(found)))
        return 0

    try:
        allowed = _load_manifest(manifest_path)
    except FileNotFoundError as exc:
        print("[错误] {}。请先执行 `python scripts/check-top-level-pyright-pragmas.py --sync`".format(exc), file=sys.stderr)
        return 1

    unexpected = sorted(found - allowed)
    stale = sorted(allowed - found)

    if not unexpected and not stale:
        print("检查通过: 顶层 `# pyright:` 指令未新增, 清单已同步")
        return 0

    if unexpected:
        print("[错误] 发现未登记的顶层 `# pyright:` 指令:", file=sys.stderr)
        for rel in unexpected:
            print("  - {}".format(rel), file=sys.stderr)
    if stale:
        print("[错误] 清单中存在已清理的条目,请同步删除:", file=sys.stderr)
        for rel in stale:
            print("  - {}".format(rel), file=sys.stderr)
    print("[提示] 可执行 `python scripts/check-top-level-pyright-pragmas.py --sync` 自动同步清单", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
