#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
检查/规范化 `.tmp/known-outer-paths-using-this-package.txt`.

设计目标:
- 允许条目使用相对仓库根目录的路径(建议),也允许保留绝对路径(兜底).
- 输出不得泄露路径明细: 仅输出统计与行号.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


DEFAULT_LIST_REL = Path(".tmp") / "known-outer-paths-using-this-package.txt"


@dataclass(frozen=True)
class _Entry:
    line_no: int
    raw: str
    kind: str  # 注释/空行/路径
    value: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_entries(list_path: Path) -> List[_Entry]:
    lines = list_path.read_text(encoding="utf-8").splitlines()
    entries: List[_Entry] = []
    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped:
            entries.append(_Entry(line_no=i, raw=raw, kind="blank", value=""))
            continue
        if stripped.startswith("#"):
            entries.append(_Entry(line_no=i, raw=raw, kind="comment", value=stripped))
            continue
        entries.append(_Entry(line_no=i, raw=raw, kind="path", value=stripped))
    return entries


def _is_abs_like(value: str) -> bool:
    if value.startswith("~"):
        return True
    return os.path.isabs(value)


def _resolve_entry_path(value: str, *, repo_root: Path) -> Optional[Path]:
    raw = value.strip()
    if not raw:
        return None
    expanded = os.path.expanduser(raw)
    p = Path(expanded)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    else:
        p = p.resolve()
    return p


def _rewrite_to_repo_relative(value: str, *, repo_root: Path) -> str:
    expanded = os.path.expanduser(value.strip())
    p = Path(expanded)
    if not p.is_absolute():
        return value.strip()
    rel = os.path.relpath(str(p), str(repo_root))
    rel_posix = Path(rel).as_posix()
    return rel_posix


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="检查/规范化 known outer paths 列表(不输出路径明细).")
    p.add_argument("--file", default=str(DEFAULT_LIST_REL), help="列表文件路径(默认: .tmp/known-outer-paths-using-this-package.txt)")
    p.add_argument("--rewrite-relative", action="store_true", help="将绝对路径条目改写为 repo-root-relative 路径(不打印路径明细).")
    p.add_argument("--require-relative", action="store_true", help="要求所有条目都是相对路径; 否则返回非零退出码.")
    p.add_argument("--check-exists", action="store_true", help="检查条目路径是否存在(仅输出行号). 默认不检查,避免 CI/环境差异误报.")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()
    list_path = Path(args.file)
    if not list_path.is_absolute():
        list_path = (repo_root / list_path).resolve()

    if not list_path.exists():
        print("未找到列表文件: {}".format(list_path))
        return 1

    entries = _load_entries(list_path)

    abs_count = 0
    rel_count = 0
    tilde_count = 0
    missing_count = 0
    problems: List[Tuple[int, str]] = []

    for e in entries:
        if e.kind != "path":
            continue
        if e.value.startswith("~"):
            tilde_count += 1
        if _is_abs_like(e.value):
            abs_count += 1
        else:
            rel_count += 1

        if args.check_exists:
            resolved = _resolve_entry_path(e.value, repo_root=repo_root)
            if resolved is None or not resolved.exists():
                missing_count += 1
                problems.append((e.line_no, "路径不存在或无法解析"))

        if args.require_relative and _is_abs_like(e.value):
            problems.append((e.line_no, "要求相对路径,但发现绝对路径或 `~` 开头路径"))

    if args.rewrite_relative:
        changed = False
        out_lines: List[str] = []
        for e in entries:
            if e.kind != "path":
                out_lines.append(e.raw)
                continue
            new_value = _rewrite_to_repo_relative(e.value, repo_root=repo_root)
            if new_value != e.value:
                changed = True
            out_lines.append(new_value)
        if changed:
            list_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")

    path_count = sum(1 for e in entries if e.kind == "path")
    print(
        "条目统计: 总计={}, 相对={}, 绝对={}, 波浪线={}, 缺失={}".format(
            path_count,
            rel_count,
            abs_count,
            tilde_count,
            missing_count if args.check_exists else "-",
        )
    )
    if args.rewrite_relative:
        print("已执行规范化写回: {}".format("有变更" if changed else "无需变更"))

    if problems:
        print("发现问题(仅输出行号):")
        for line_no, reason in problems[:50]:
            print("- L{}: {}".format(line_no, reason))
        if len(problems) > 50:
            print("- ... (共 {} 处,已截断)".format(len(problems)))
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
