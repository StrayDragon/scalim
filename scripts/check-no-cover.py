#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ruff: noqa: T201
# force-en
"""扫描源码中的 `# pragma: no cover` 使用.

设计目标:
- 为 `# pragma: no cover` 建立可审阅基线,防止覆盖率门禁被隐式绕开.
- 允许对确属必要的例外做显式标记:
  - 行级: `# pragma: allow-no-cover <reason>`
  - 文件级: `# pragma: allow-no-cover-file <reason>`
- allow pragma 属于治理标记;在测试或结构重构完成前不要直接删除.

用法:
    `uv run scripts/check-no-cover.py`
    `uv run scripts/check-no-cover.py --json`
    `uv run scripts/check-no-cover.py --check`
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence


_NO_COVER_MARK = "pragma: no cover"
_ALLOW_MARK = "pragma: allow-no-cover"
_ALLOW_FILE_MARK = "pragma: allow-no-cover-file"
_DEFAULT_REL_ROOTS = (Path("src") / "scalim", Path("tests"), Path("scripts"))
_DEFAULT_TEXT_REPORT_REL = Path(".tmp") / "artifacts" / "no-cover.report.txt"
_DEFAULT_JSON_REPORT_REL = Path(".tmp") / "artifacts" / "no-cover.report.json"


@dataclass(frozen=True)
class _CommentPolicy:
    allow_lines: dict[int, str]
    comment_lines: set[int]
    allow_file_reason: str


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    col: int
    pragma_text: str
    status: str
    allow_reason: str


def _is_excluded(path: Path) -> bool:
    excluded_parts = {
        ".git",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "site",
        "dist",
        "build",
        "node_modules",
        ".tmp",
        "vendor",
    }
    return any(part in excluded_parts for part in path.parts)


def _resolve_input_path(*, repo_root: Path, raw_path: Path) -> Optional[Path]:
    candidate = raw_path if raw_path.is_absolute() else (repo_root / raw_path)
    resolved = candidate.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        return None
    rel = resolved.relative_to(repo_root)
    if _is_excluded(rel):
        return None
    return resolved


def _iter_python_files(*, repo_root: Path, rel_roots: Sequence[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for rel_root in rel_roots:
        root = _resolve_input_path(repo_root=repo_root, raw_path=rel_root)
        if root is None or not root.exists():
            continue
        paths = (root,) if root.is_file() else root.rglob("*.py")
        for path in paths:
            if path.suffix != ".py":
                continue
            if path != repo_root and repo_root not in path.parents:
                continue
            rel = path.relative_to(repo_root)
            if _is_excluded(rel) or path in seen:
                continue
            seen.add(path)
            yield path


def _reason_after_marker(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].strip()


def _parse_comment_policy(source: str) -> _CommentPolicy:
    allow_lines: dict[int, str] = {}
    comment_lines: set[int] = set()
    allow_file_reason = ""
    in_header = True

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            line = int(token.start[0])
            stripped = token.string.lstrip("#").strip()
            comment_lines.add(line)
            if in_header and _ALLOW_FILE_MARK in stripped:
                reason = _reason_after_marker(stripped, _ALLOW_FILE_MARK)
                if reason:
                    allow_file_reason = reason
            if _ALLOW_MARK in stripped:
                reason = _reason_after_marker(stripped, _ALLOW_MARK)
                if reason:
                    allow_lines[line] = reason
            continue

        if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.STRING and int(token.start[0]) == 1:
            continue
        in_header = False

    return _CommentPolicy(allow_lines=allow_lines, comment_lines=comment_lines, allow_file_reason=allow_file_reason)


def _allow_reason_for(*, line: int, pragma_text: str, comment_policy: _CommentPolicy) -> str:
    if comment_policy.allow_file_reason:
        return comment_policy.allow_file_reason

    same_line_reason = _reason_after_marker(pragma_text, _ALLOW_MARK)
    if same_line_reason:
        return same_line_reason

    previous_line = line - 1
    if previous_line in comment_policy.comment_lines:
        return comment_policy.allow_lines.get(previous_line, "")

    return comment_policy.allow_lines.get(line, "")


def _scan_file(path: Path) -> list[_Hit]:
    source = path.read_text(encoding="utf-8")
    comment_policy = _parse_comment_policy(source)
    hits: list[_Hit] = []

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        stripped = token.string.lstrip("#").strip()
        if _NO_COVER_MARK not in stripped:
            continue
        allow_reason = _allow_reason_for(line=int(token.start[0]), pragma_text=stripped, comment_policy=comment_policy)
        hits.append(
            _Hit(
                path=path,
                line=int(token.start[0]),
                col=int(token.start[1]) + 1,
                pragma_text=stripped,
                status="allow" if allow_reason else "block",
                allow_reason=allow_reason,
            )
        )

    return sorted(hits, key=lambda item: (item.line, item.col, item.pragma_text))


def scan_repo(*, repo_root: Path, rel_roots: Sequence[Path]) -> list[_Hit]:
    hits: list[_Hit] = []
    for path in _iter_python_files(repo_root=repo_root, rel_roots=rel_roots):
        hits.extend(_scan_file(path))
    return sorted(hits, key=lambda item: (str(item.path), item.line, item.col, item.pragma_text))


def _count_by_file(*, repo_root: Path, hits: Sequence[_Hit], status: Optional[str] = None) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for hit in hits:
        if status is not None and hit.status != status:
            continue
        rel = hit.path.relative_to(repo_root).as_posix()
        counts[rel] = counts.get(rel, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _render_text_report(*, repo_root: Path, hits: Sequence[_Hit], show_allow_details: bool = False) -> str:
    total = len(hits)
    blocked = sum(1 for hit in hits if hit.status == "block")
    allowed = total - blocked

    lines = [
        "no-cover 扫描报告",
        "",
        "摘要:",
        "  total={} block={} allow={}".format(total, blocked, allowed),
    ]

    top_files = _count_by_file(repo_root=repo_root, hits=hits)
    if top_files:
        lines.extend(["", "热点文件(按总命中数排序):"])
        for rel, count in top_files[:20]:
            lines.append("  {} {}".format(str(count).rjust(3), rel))

    lines.extend(
        [
            "",
            "规避建议:",
            "  1. 可测试分支优先补测试,不要先加 `# pragma: no cover`.",
            "  2. 抽象边界/兼容兜底等确属必要场景,在同一行或上一行加 `# pragma: allow-no-cover <reason>`.",
            "  3. 文件整体承担兼容/框架职责时,在文件头注释区加 `# pragma: allow-no-cover-file <reason>`.",
            "  4. allow pragma 属于治理标记;未完成替代前不要直接删除.",
        ]
    )

    if hits:
        detail_hits = [hit for hit in hits if hit.status != "allow" or show_allow_details]
        if detail_hits:
            lines.extend(["", "明细:"])
            for hit in detail_hits:
                rel = hit.path.relative_to(repo_root).as_posix()
                suffix = " reason={}".format(hit.allow_reason) if hit.allow_reason else ""
                lines.append("  [{}] {}:{}:{}{} text={}".format(hit.status.upper(), rel, hit.line, hit.col, suffix, hit.pragma_text))
        if allowed and not show_allow_details:
            lines.extend(["", "allow 明细默认省略; 如需展开,运行 `uv run scripts/check-no-cover.py --show-allow-details`."])
    else:
        lines.extend(["", "未发现 `# pragma: no cover`."])

    return "\n".join(lines) + "\n"


def _render_json(*, repo_root: Path, hits: Sequence[_Hit]) -> str:
    payload = {
        "summary": {
            "total": len(hits),
            "block": sum(1 for hit in hits if hit.status == "block"),
            "allow": sum(1 for hit in hits if hit.status == "allow"),
            "by_file": [{"path": rel, "count": count} for rel, count in _count_by_file(repo_root=repo_root, hits=hits)],
        },
        "hits": [
            {
                "path": hit.path.relative_to(repo_root).as_posix(),
                "line": hit.line,
                "col": hit.col,
                "pragma_text": hit.pragma_text,
                "status": hit.status,
                "allow_reason": hit.allow_reason,
            }
            for hit in hits
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描源码中的 `# pragma: no cover` 使用.")
    parser.add_argument("paths", nargs="*", help="要扫描的路径(默认: `src/scalim` / `tests` / `scripts`).")
    parser.add_argument("--json", action="store_true", help="输出 JSON.")
    parser.add_argument("--report", default="", help="覆盖默认文本报告路径.")
    parser.add_argument("--no-artifacts", action="store_true", help="不自动写入 `.tmp/artifacts/no-cover.report.{txt,json}`.")
    parser.add_argument("--check", action="store_true", help="若存在未 allow 的命中则返回非零退出码.")
    parser.add_argument("--show-allow-details", action="store_true", help="文本报告中展开 `allow` 明细.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    rel_roots = tuple(Path(path) for path in args.paths) if args.paths else _DEFAULT_REL_ROOTS
    hits = scan_repo(repo_root=repo_root, rel_roots=rel_roots)

    text_report = _render_text_report(repo_root=repo_root, hits=hits, show_allow_details=args.show_allow_details)
    json_report = _render_json(repo_root=repo_root, hits=hits)
    output = json_report if args.json else text_report

    if not args.no_artifacts:
        text_report_path = _DEFAULT_TEXT_REPORT_REL if not args.report else Path(args.report)
        text_report_abs = (text_report_path if text_report_path.is_absolute() else repo_root / text_report_path).resolve()
        json_report_abs = (repo_root / _DEFAULT_JSON_REPORT_REL).resolve()
        text_report_abs.parent.mkdir(parents=True, exist_ok=True)
        json_report_abs.parent.mkdir(parents=True, exist_ok=True)
        text_report_abs.write_text(text_report, encoding="utf-8")
        json_report_abs.write_text(json_report, encoding="utf-8")
    elif args.report:
        report_path = (Path(args.report) if Path(args.report).is_absolute() else repo_root / args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text_report, encoding="utf-8")

    # `--check` 模式无违规时不在 `stdout` 输出(静默通过)
    if not args.check or any(hit.status == "block" for hit in hits):
        sys.stdout.write(output)

    if args.check and any(hit.status == "block" for hit in hits):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
