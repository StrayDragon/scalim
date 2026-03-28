#!/usr/bin/env python3
"""检查用户材料不得引用内部/不安全导入路径.

扫描范围(用户可见材料):
- `docs/doc/**`
- `artifacts/skills/**`

本检查是“窄且确定”的黑名单扫描,用于避免把内部/不安全入口扩散为公开教程.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class Hit:
    relpath: str
    lineno: int
    token: str
    line: str


_TEXT_SUFFIXES: Tuple[str, ...] = (
    ".md",
    ".txt",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
)

_BANNED_TOKENS: Tuple[str, ...] = (
    # `YAML DSL` 内部/不安全入口
    "scalim.dsl.by_yaml.runtime.unsafe_entrypoints",
    "unsafe_entrypoints",
    # `allowlist` 的 `trusted-mode` 逃逸口(禁止出现在用户材料)
    "trusted_allow_all_modules",
    "TRUSTED_ALLOW_ALL_MODULES",
)


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        yield path


def _scan_file(path: Path, *, repo_root: Path) -> List[Hit]:
    rel = str(path.relative_to(repo_root))
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return [Hit(relpath=rel, lineno=1, token="(read-error)", line="{}: {}".format(type(exc).__name__, exc))]

    hits: List[Hit] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for token in _BANNED_TOKENS:
            if token in line:
                hits.append(Hit(relpath=rel, lineno=idx, token=token, line=line.rstrip()))
    return hits


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 docs/skills 不得引用内部/不安全导入路径.")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument("--docs-root", default="docs/doc", help="文档根目录(默认: docs/doc).")
    parser.add_argument("--skills-root", default="artifacts/skills", help="skills 根目录(默认: artifacts/skills).")
    parser.add_argument("--check", action="store_true", help="执行检查; 发现问题时返回非 0 退出码.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()
    docs_root = (repo_root / str(args.docs_root)).resolve()
    skills_root = (repo_root / str(args.skills_root)).resolve()

    hits: List[Hit] = []
    for root in (docs_root, skills_root):
        for path in sorted(_iter_text_files(root)):
            hits.extend(_scan_file(path, repo_root=repo_root))

    if hits:
        print("[错误] 用户材料导入边界检查失败 ({} 处命中):".format(len(hits)), file=sys.stderr)
        for hit in hits:
            print("- {}:{}: 禁止引用 {!r}: {}".format(hit.relpath, hit.lineno, hit.token, hit.line), file=sys.stderr)
        print("", file=sys.stderr)
        print("迁移建议:", file=sys.stderr)
        print("- 将 YAML DSL 调用示例统一迁移到 `from scalim.dsl.by_yaml import run, compile`。", file=sys.stderr)
        print(
            "- 使用 `allowed_modules`/`allowed_functions` 显式 `allowlist`; 不要在公开材料中展示 `allowlist` 的不安全逃逸口。",
            file=sys.stderr,
        )
        print("- 如确需内部不安全能力,请走内部受控流程(不在公开 `docs/doc/**` 与 `artifacts/skills/**` 中引用).", file=sys.stderr)
        return 1

    print("[通过] 用户材料导入边界检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
