#!/usr/bin/env python3
"""检查用户材料导入边界(禁止内部/未编目导入).

扫描范围(用户可见材料):
- `docs/doc/**`
- `notebooks/marimo/**`
- `agentdev/skills/**`

跳过:
- `**/references/upgrades/**`(迁移指南需要展示 Before 反例/旧内部路径)

约束(约定优先):
- 用户材料中不得出现内部/不安全导入路径(例如 `._internal`、`._foo`、`runtime.*` 等)

输出合约:
- `--check` 只控制退出码(发现问题时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Hit:
    relpath: str
    lineno: int
    kind: str
    token: str
    line: str
    suggestion: str


_TEXT_SUFFIXES: Tuple[str, ...] = (
    ".md",
    ".txt",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
)

_SCALIM_IMPORT_RE = re.compile(r"(?:\bfrom\s+(scalim(?:\.[A-Za-z0-9_]+)*)\s+import\b)|(?:\bimport\s+(scalim(?:\.[A-Za-z0-9_]+)*)\b)")

# `scalim.events._foo` 命中; 不误伤 `scalim.events.__all__`
_EVENTS_INTERNAL_TOKEN_RE = re.compile(r"scalim\.events\._(?!_)")

_INTERNAL_TOKEN_SUGGESTIONS: Mapping[str, str] = {
    # “硬禁止”标记(不要求是 `import` 语句;出现在任何用户材料文本中都应立即报错)
    "TRUSTED_ALLOW_ALL_MODULES": "请移除该内部/不安全标记;用户材料不得放宽导入边界.",
    "trusted_allow_all_modules": "请移除该内部/不安全标记;用户材料不得放宽导入边界.",
    "scalim.vendor.literich": "`scalim.vendor.literich` 已移除;请勿在 docs/skills/notebooks 中引用该模块.",
    "unsafe_entrypoints": "请勿在用户材料中引用内部/不安全入口;优先使用稳定的 facade 入口.",
    # 内部实现路径(常见误用)
    "scalim.dsl.yaml_dsl._internal.": "请勿导入内部实现;优先使用 `scalim.dsl.yaml_dsl` 或其稳定子模块.",
    "scalim.dsl.yaml_dsl.runtime.": "请勿导入内部实现;优先使用 `scalim.dsl.yaml_dsl` 或其稳定子模块.",
    "scalim.dsl.yaml_dsl.schema_dsl.": "请勿导入内部实现;优先使用 `scalim.dsl.yaml_dsl` 或其稳定子模块.",
    "scalim.events._": "请勿导入内部实现;优先使用 `scalim.events`.",
    "scalim.sinks._internal.": "请勿导入内部实现;优先使用 `scalim.sinks`.",
}


def _is_skipped(relpath: str) -> bool:
    """迁移指南允许展示旧内部路径 Before 反例."""
    parts = Path(relpath).parts
    try:
        idx = parts.index("references")
    except ValueError:
        return False
    return idx + 1 < len(parts) and parts[idx + 1] == "upgrades"


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        yield path


def _line_has_internal_token(line: str, token: str) -> bool:
    if not token:
        return False
    if token == "scalim.events._":
        return _EVENTS_INTERNAL_TOKEN_RE.search(line) is not None
    return token in line


def _scan_file(
    path: Path,
    *,
    repo_root: Path,
    internal_token_suggestions: Mapping[str, str],
) -> List[Hit]:
    rel = str(path.relative_to(repo_root))
    if _is_skipped(rel):
        return []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return [
            Hit(
                relpath=rel,
                lineno=1,
                kind="read-error",
                token="(read-error)",
                line="{}: {}".format(type(exc).__name__, exc),
                suggestion="请检查文件编码或权限.",
            )
        ]

    hits: List[Hit] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.rstrip()

        # 1) 内部/不安全 标记/前缀 门禁(窄且确定)
        for token, suggestion in internal_token_suggestions.items():
            if _line_has_internal_token(stripped, token):
                hits.append(
                    Hit(
                        relpath=rel,
                        lineno=idx,
                        kind="internal",
                        token=token,
                        line=stripped,
                        suggestion=str(suggestion or "").strip()
                        or "请移除内部/不安全 token; 优先使用更上层的 facade 模块导入(例如 `scalim.dsl.yaml_dsl`/`scalim.events`/`scalim.sinks`).",
                    )
                )

        # 2) `scalim.*` 内部导入门禁(约定: `._internal` 或 `._foo` 都属于内部实现)
        match = _SCALIM_IMPORT_RE.search(stripped)
        if not match:
            continue
        module_name = match.group(1) or match.group(2) or ""
        module_name = str(module_name).strip()
        if not module_name:
            continue
        if module_name == "scalim":
            continue

        parts = [p for p in module_name.split(".") if p]
        internal_parts = [p for p in parts[1:] if p.startswith("_")]
        if "_internal" in parts or internal_parts:
            hint = "请勿导入内部实现;优先从更上层的 facade 模块导入(例如 `scalim.dsl.yaml_dsl`/`scalim.events`/`scalim.sinks`)."
            hits.append(
                Hit(
                    relpath=rel,
                    lineno=idx,
                    kind="internal-import",
                    token=module_name,
                    line=stripped,
                    suggestion=hint,
                )
            )
    return hits


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 docs/skills 不得引用内部/不安全导入路径.")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument("--docs-root", default="docs/doc", help="文档根目录(默认: docs/doc).")
    parser.add_argument("--notebooks-root", default="notebooks/marimo", help="notebooks 根目录(默认: notebooks/marimo).")
    parser.add_argument("--skills-root", default="agentdev/skills", help="skills 根目录(默认: agentdev/skills).")
    parser.add_argument("--check", action="store_true", help="执行检查; 发现问题时返回非 0 退出码.")
    parser.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()
    docs_root = (repo_root / str(args.docs_root)).resolve()
    notebooks_root = (repo_root / str(args.notebooks_root)).resolve()
    skills_root = (repo_root / str(args.skills_root)).resolve()

    hits: List[Hit] = []
    for root in (docs_root, notebooks_root, skills_root):
        for path in sorted(_iter_text_files(root)):
            hits.extend(
                _scan_file(
                    path,
                    repo_root=repo_root,
                    internal_token_suggestions=_INTERNAL_TOKEN_SUGGESTIONS,
                )
            )

    if hits:
        print("[错误] 用户材料导入边界检查失败 ({} 处命中):".format(len(hits)), file=sys.stderr)
        for hit in hits:
            print(
                "- {}:{}: [{}] 命中={!r}: {}".format(hit.relpath, hit.lineno, hit.kind, hit.token, hit.line),
                file=sys.stderr,
            )
            print("  建议: {}".format(hit.suggestion), file=sys.stderr)
        print("", file=sys.stderr)
        print("迁移建议:", file=sys.stderr)
        print(
            "- 禁止把 `internal/unsafe` 路径写进教程/示例(尤其是 `dsl.yaml_dsl.runtime.*`/`events._*`/`sinks._internal.*`).",
            file=sys.stderr,
        )
        print("- 优先使用更上层的门面模块导入(例如 `scalim.dsl.yaml_dsl`/`scalim.events`/`scalim.sinks`).", file=sys.stderr)
        return 1

    if not args.quiet:
        print("[通过] 用户材料导入边界检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
