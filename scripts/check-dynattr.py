#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ruff: noqa: T201
"""扫描源码中的 `getattr` / `setattr` / `hasattr` 调用.

设计目标:
- 为 `dynattr` 治理提供可审阅基线,默认先“报告”,再逐步收紧到 `QA` 门禁.
- 允许对确属必要的动态场景做显式例外,避免隐式扩散:
  - 行级: `# pragma: allow-dynattr <prefix>: <detail>`
  - 文件级: `# pragma: allow-dynattr-file <prefix>: <detail>`
  - `prefix` 可选: `compat` / `dispatch` / `dsl` / `introspection` / `legacy` / `metadata` / `optional-interface` / `plugin` / `third-party`
- `allow pragma` 属于治理标记;在未完成静态化重构或替代说明前,不要直接删除.
- 输出尽量贴近重构决策: 给出位置、调用类型、属性表达式摘要与 `allow` 理由.

用法:
    `uv run scripts/check-dynattr.py`
    `uv run scripts/check-dynattr.py --json`
    `uv run scripts/check-dynattr.py --check`
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence


_DYNATTR_ALLOW_MARK = "pragma: allow-dynattr"
_DYNATTR_ALLOW_FILE_MARK = "pragma: allow-dynattr-file"
_TARGET_CALLS = frozenset({"getattr", "setattr", "hasattr"})
_DEFAULT_REL_ROOTS = (Path("src") / "scalim",)
_DEFAULT_TEXT_REPORT_REL = Path(".tmp") / "artifacts" / "dynattr.report.txt"
_DEFAULT_JSON_REPORT_REL = Path(".tmp") / "artifacts" / "dynattr.report.json"
_ALLOW_REASON_PREFIXES = frozenset(
    {
        "compat",
        "dispatch",
        "dsl",
        "introspection",
        "legacy",
        "metadata",
        "optional-interface",
        "plugin",
        "third-party",
    }
)


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    col: int
    end_line: int
    end_col: int
    call_name: str
    attr_expr: str
    status: str
    allow_reason: str


@dataclass(frozen=True)
class _CommentPolicy:
    allow_lines: dict[int, str]
    allow_file_reason: str


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
        if root is None:
            continue
        if not root.exists():
            continue
        paths: Iterable[Path]
        if root.is_file():
            if root.suffix != ".py":
                continue
            paths = (root,)
        else:
            paths = root.rglob("*.py")
        for path in paths:
            if path != repo_root and repo_root not in path.parents:
                continue
            rel = path.relative_to(repo_root)
            if _is_excluded(rel):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def _reason_after_marker(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].strip()


def _normalize_allow_reason(reason: str) -> str:
    """
    `allow` 理由属于治理标记,需要可审阅且可聚类.

    约定格式: `<prefix>: <detail>`
    - `prefix` 必须在 `_ALLOW_REASON_PREFIXES` 中
    - `detail` 不能为空
    """

    stripped = reason.strip()
    if not stripped:
        return ""
    if ":" not in stripped:
        return ""
    prefix, detail = stripped.split(":", 1)
    prefix = prefix.strip()
    detail = detail.strip()
    if prefix not in _ALLOW_REASON_PREFIXES:
        return ""
    if not detail:
        return ""
    return "{}: {}".format(prefix, detail)


def _parse_comment_policy(source: str) -> _CommentPolicy:
    allow_lines: dict[int, str] = {}
    allow_file_reason = ""
    in_header = True

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            line = int(token.start[0])
            stripped = token.string.lstrip("#").strip()
            if _DYNATTR_ALLOW_FILE_MARK in stripped and in_header:
                reason = _reason_after_marker(stripped, _DYNATTR_ALLOW_FILE_MARK)
                normalized = _normalize_allow_reason(reason)
                if normalized:
                    allow_file_reason = normalized
            if _DYNATTR_ALLOW_MARK in stripped:
                reason = _reason_after_marker(stripped, _DYNATTR_ALLOW_MARK)
                normalized = _normalize_allow_reason(reason)
                if normalized:
                    allow_lines[line] = normalized
            continue

        if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.STRING and int(token.start[0]) == 1:
            continue
        in_header = False

    return _CommentPolicy(allow_lines=allow_lines, allow_file_reason=allow_file_reason)


def _resolve_call_name(node: ast.Call) -> Optional[str]:
    func = node.func
    if isinstance(func, ast.Name) and func.id in _TARGET_CALLS:
        return func.id
    if isinstance(func, ast.Attribute) and func.attr in _TARGET_CALLS:
        if isinstance(func.value, ast.Name) and func.value.id == "builtins":
            return func.attr
    return None


def _node_end_line(node: ast.AST) -> int:
    end_line = getattr(node, "end_lineno", None)
    if isinstance(end_line, int) and end_line > 0:
        return end_line
    return int(getattr(node, "lineno", 0) or 0)


def _node_end_col(node: ast.AST) -> int:
    end_col = getattr(node, "end_col_offset", None)
    if isinstance(end_col, int) and end_col > 0:
        return end_col
    return int(getattr(node, "col_offset", 0) or 0)


def _is_allowed(*, node: ast.Call, comment_policy: _CommentPolicy) -> bool:
    return bool(_allow_reason_for(node=node, comment_policy=comment_policy))


def _allow_reason_for(*, node: ast.Call, comment_policy: _CommentPolicy) -> str:
    if comment_policy.allow_file_reason:
        return comment_policy.allow_file_reason
    start = int(getattr(node, "lineno", 0) or 0)
    end = _node_end_line(node)
    for line in range(start, end + 1):
        reason = comment_policy.allow_lines.get(line, "")
        if reason:
            return reason
    return ""


def _summarize_expr(source: str, node: Optional[ast.AST]) -> str:
    if node is None:
        return "<missing>"
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return "<unknown>"
    compact = " ".join(str(segment).split())
    if len(compact) <= 80:
        return compact
    return compact[:77] + "..."


def _scan_file(path: Path) -> list[_Hit]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.as_posix())
    comment_policy = _parse_comment_policy(source)

    hits: list[_Hit] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _resolve_call_name(node)
        if call_name is None:
            continue

        attr_node = node.args[1] if len(node.args) >= 2 else None
        allow_reason = _allow_reason_for(node=node, comment_policy=comment_policy)
        hits.append(
            _Hit(
                path=path,
                line=int(getattr(node, "lineno", 0) or 0),
                col=int(getattr(node, "col_offset", 0) or 0) + 1,
                end_line=_node_end_line(node),
                end_col=_node_end_col(node),
                call_name=call_name,
                attr_expr=_summarize_expr(source, attr_node),
                status="allow" if allow_reason else "block",
                allow_reason=allow_reason,
            )
        )
    return sorted(hits, key=lambda item: (item.line, item.col, item.call_name, item.attr_expr))


def scan_repo(*, repo_root: Path, rel_roots: Sequence[Path]) -> list[_Hit]:
    hits: list[_Hit] = []
    for path in _iter_python_files(repo_root=repo_root, rel_roots=rel_roots):
        hits.extend(_scan_file(path))
    return sorted(hits, key=lambda item: (str(item.path), item.line, item.col, item.call_name, item.attr_expr))


def _count_by_call(hits: Iterable[_Hit], *, status: Optional[str] = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        if status is not None and hit.status != status:
            continue
        counts[hit.call_name] = counts.get(hit.call_name, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _count_by_file(*, repo_root: Path, hits: Iterable[_Hit], status: Optional[str] = None) -> list[tuple[str, int]]:
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

    lines: list[str] = []
    lines.append("dynattr 扫描报告")
    lines.append("")
    lines.append("摘要:")
    lines.append("  total={} block={} allow={}".format(total, blocked, allowed))

    call_counts = _count_by_call(hits)
    if call_counts:
        lines.append("  calls={}".format(", ".join("{}={}".format(name, count) for name, count in call_counts.items())))

    top_files = _count_by_file(repo_root=repo_root, hits=hits)
    if top_files:
        lines.append("")
        lines.append("热点文件(按总命中数排序):")
        for rel, count in top_files[:20]:
            lines.append("  {} {}".format(str(count).rjust(3), rel))

    lines.append("")
    lines.append("规避建议:")
    lines.append("  1. 已知固定字段时,改为直接属性访问 `obj.attr`.")
    lines.append("  2. 分支已知时,改为显式 `if/elif` 或 dispatch table,不要拼接 handler 名后再 `getattr`.")
    lines.append("  3. 结构可约束时,引入 `Protocol` / dataclass / 明确接口,把字段名收敛到类型系统.")
    lines.append("  4. 确属动态框架点时,在调用行加 `# pragma: allow-dynattr <prefix>: <detail>`.")
    lines.append("  5. 文件整体必须动态时,在文件头注释区加 `# pragma: allow-dynattr-file <prefix>: <detail>`.")
    lines.append("  6. allow pragma 属于治理标记;未完成替代前不要直接删除.")

    if hits:
        detail_hits = [hit for hit in hits if hit.status != "allow" or show_allow_details]
        if detail_hits:
            lines.append("")
            lines.append("明细:")
            for hit in detail_hits:
                rel = hit.path.relative_to(repo_root).as_posix()
                suffix = " reason={}".format(hit.allow_reason) if hit.allow_reason else ""
                lines.append(
                    "  [{}] {}:{}:{} {}{} attr={}".format(
                        hit.status.upper(),
                        rel,
                        hit.line,
                        hit.col,
                        hit.call_name,
                        suffix,
                        hit.attr_expr,
                    )
                )
        if allowed and not show_allow_details:
            lines.append("")
            lines.append("allow 明细默认省略; 如需展开,运行 `uv run scripts/check-dynattr.py --show-allow-details`.")
    else:
        lines.append("")
        lines.append("未发现 dynattr 调用.")

    return "\n".join(lines) + "\n"


def _render_json(*, repo_root: Path, hits: Sequence[_Hit]) -> str:
    payload = {
        "summary": {
            "total": len(hits),
            "block": sum(1 for hit in hits if hit.status == "block"),
            "allow": sum(1 for hit in hits if hit.status == "allow"),
            "by_call": _count_by_call(hits),
            "by_file": [{"path": rel, "count": count} for rel, count in _count_by_file(repo_root=repo_root, hits=hits)],
        },
        "hits": [
            {
                "path": hit.path.relative_to(repo_root).as_posix(),
                "line": hit.line,
                "col": hit.col,
                "end_line": hit.end_line,
                "end_col": hit.end_col,
                "call_name": hit.call_name,
                "attr_expr": hit.attr_expr,
                "status": hit.status,
                "allow_reason": hit.allow_reason,
            }
            for hit in hits
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描源码中的 `getattr` / `setattr` / `hasattr` 调用.")
    parser.add_argument("paths", nargs="*", help="要扫描的路径(默认: `src/scalim`).")
    parser.add_argument("--json", action="store_true", help="输出 JSON.")
    parser.add_argument("--report", default="", help="覆盖默认文本报告路径.")
    parser.add_argument("--no-artifacts", action="store_true", help="不自动写入 `.tmp/artifacts/dynattr.report.{txt,json}`.")
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
