#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ruff: noqa: T201
"""扫描源码中的类型标注 `object` 使用.

设计目标:
- 为 `object` 类型逃逸点建立可审阅基线,推动用更精确的类型范式替代 `object`/`Any`.
- 允许对确属必要的动态边界做显式例外:
  - 行级: `# pragma: allow-object <reason>`
  - 文件级: `# pragma: allow-object-file <reason>`
- `scripts/` 与 `vendor/` 属于白名单边界: 命中会被标记为 `whitelist`,不参与 `--check` 阻断.

用法:
    `uv run scripts/check-object-type.py`
    `uv run scripts/check-object-type.py --json`
    `uv run scripts/check-object-type.py --check`
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence


_ALLOW_MARK = "pragma: allow-object"
_ALLOW_FILE_MARK = "pragma: allow-object-file"
_DEFAULT_REL_ROOTS = (Path("src") / "scalim", Path("tests"), Path("scripts"))
_DEFAULT_TEXT_REPORT_REL = Path(".tmp") / "artifacts" / "object-type.report.txt"
_DEFAULT_JSON_REPORT_REL = Path(".tmp") / "artifacts" / "object-type.report.json"
_OBJECT_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])object(?![A-Za-z0-9_])")


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
    end_line: int
    end_col: int
    kind: str
    summary: str
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


def _is_whitelisted(rel_path: Path) -> bool:
    return "scripts" in rel_path.parts


def _resolve_input_path(*, repo_root: Path, raw_path: Path) -> Optional[Path]:
    candidate = raw_path if raw_path.is_absolute() else (repo_root / raw_path)
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(repo_root)
    except ValueError:
        return None
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
            try:
                rel = path.relative_to(repo_root)
            except ValueError:
                continue
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


def _allow_reason_for(*, line: int, comment_policy: _CommentPolicy) -> str:
    if comment_policy.allow_file_reason:
        return comment_policy.allow_file_reason
    direct = comment_policy.allow_lines.get(line, "")
    if direct:
        return direct
    previous_line = line - 1
    if previous_line in comment_policy.comment_lines:
        return comment_policy.allow_lines.get(previous_line, "")
    return ""


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


def _is_object_ref(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "object":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "object":
        value = node.value
        return isinstance(value, ast.Name) and value.id == "builtins"
    return False


def _annotation_contains_object(annotation: ast.AST) -> bool:
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return bool(_OBJECT_TOKEN_RE.search(annotation.value))
    for child in ast.walk(annotation):
        if _is_object_ref(child):
            return True
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and _OBJECT_TOKEN_RE.search(child.value):
            return True
    return False


def _scan_file(*, repo_root: Path, path: Path) -> list[_Hit]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.as_posix())
    comment_policy = _parse_comment_policy(source)
    rel = path.relative_to(repo_root)
    whitelisted = _is_whitelisted(rel)

    hits: list[_Hit] = []

    def add_hit(*, node: ast.AST, kind: str, summary: str) -> None:
        line = int(getattr(node, "lineno", 0) or 0)
        col = int(getattr(node, "col_offset", 0) or 0) + 1
        allow_reason = _allow_reason_for(line=line, comment_policy=comment_policy)
        status = "whitelist" if whitelisted else ("allow" if allow_reason else "block")
        hits.append(
            _Hit(
                path=path,
                line=line,
                col=col,
                end_line=_node_end_line(node),
                end_col=_node_end_col(node),
                kind=kind,
                summary=summary,
                status=status,
                allow_reason=allow_reason,
            )
        )

    for stmt in tree.body:
        if isinstance(stmt, ast.AnnAssign) and stmt.annotation is not None:
            if _annotation_contains_object(stmt.annotation):
                target = ast.get_source_segment(source, stmt.target) or "<unknown>"
                add_hit(node=stmt.annotation, kind="annassign", summary="target={}".format(" ".join(target.split())))

        if isinstance(stmt, ast.Assign):
            if _is_object_ref(stmt.value):
                for target in stmt.targets:
                    name = ast.get_source_segment(source, target) or "<unknown>"
                    add_hit(node=stmt.value, kind="alias", summary="target={}".format(" ".join(str(name).split())))

        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_name = str(getattr(stmt, "name", "") or "")
            returns = stmt.returns
            if returns is not None and _annotation_contains_object(returns):
                add_hit(node=returns, kind="return", summary="fn={}".format(fn_name))
            for arg in list(stmt.args.posonlyargs) + list(stmt.args.args) + list(stmt.args.kwonlyargs):
                if arg.annotation is not None and _annotation_contains_object(arg.annotation):
                    add_hit(node=arg.annotation, kind="param", summary="fn={} arg={}".format(fn_name, arg.arg))
            if stmt.args.vararg is not None and stmt.args.vararg.annotation is not None:
                if _annotation_contains_object(stmt.args.vararg.annotation):
                    add_hit(
                        node=stmt.args.vararg.annotation,
                        kind="param",
                        summary="fn={} arg=*{}".format(fn_name, stmt.args.vararg.arg),
                    )
            if stmt.args.kwarg is not None and stmt.args.kwarg.annotation is not None:
                if _annotation_contains_object(stmt.args.kwarg.annotation):
                    add_hit(
                        node=stmt.args.kwarg.annotation,
                        kind="param",
                        summary="fn={} arg=**{}".format(fn_name, stmt.args.kwarg.arg),
                    )

        if isinstance(stmt, ast.ClassDef):
            cls_name = str(getattr(stmt, "name", "") or "")
            for item in stmt.body:
                if isinstance(item, ast.AnnAssign) and item.annotation is not None and _annotation_contains_object(item.annotation):
                    target = ast.get_source_segment(source, item.target) or "<unknown>"
                    add_hit(
                        node=item.annotation,
                        kind="class-annassign",
                        summary="cls={} target={}".format(cls_name, " ".join(str(target).split())),
                    )

    return sorted(hits, key=lambda item: (item.line, item.col, item.kind, item.summary))


def scan_repo(*, repo_root: Path, rel_roots: Sequence[Path]) -> list[_Hit]:
    hits: list[_Hit] = []
    for path in _iter_python_files(repo_root=repo_root, rel_roots=rel_roots):
        hits.extend(_scan_file(repo_root=repo_root, path=path))
    return sorted(hits, key=lambda item: (str(item.path), item.line, item.col, item.kind, item.summary))


def _count_by_file(*, repo_root: Path, hits: Iterable[_Hit], status: Optional[str] = None) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for hit in hits:
        if status is not None and hit.status != status:
            continue
        rel = hit.path.relative_to(repo_root).as_posix()
        counts[rel] = counts.get(rel, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _count_by_kind(hits: Iterable[_Hit]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit.kind] = counts.get(hit.kind, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _render_text_report(*, repo_root: Path, hits: Sequence[_Hit]) -> str:
    total = len(hits)
    blocked = sum(1 for hit in hits if hit.status == "block")
    allowed = sum(1 for hit in hits if hit.status == "allow")
    whitelisted = sum(1 for hit in hits if hit.status == "whitelist")

    lines: list[str] = []
    lines.append("object 类型标注扫描报告")
    lines.append("")
    lines.append("摘要:")
    lines.append("  total={} block={} allow={} whitelist={}".format(total, blocked, allowed, whitelisted))

    kind_counts = _count_by_kind(hits)
    if kind_counts:
        lines.append("  kinds={}".format(", ".join("{}={}".format(kind, count) for kind, count in kind_counts.items())))

    top_files = _count_by_file(repo_root=repo_root, hits=hits)
    if top_files:
        lines.append("")
        lines.append("热点文件(按总命中数排序):")
        for rel, count in top_files[:20]:
            lines.append("  {} {}".format(str(count).rjust(3), rel))

    lines.append("")
    lines.append("规避建议:")
    lines.append("  1. 已知结构时,优先收紧签名/字段类型,不要直接写 `object`.")
    lines.append("  2. 可抽象接口时,优先 `Protocol`/ABC/显式运行时契约.")
    lines.append("  3. JSON 结构时,优先 `TypedDict`/递归别名(例如 JsonLike),避免顶层 `object` 扩散.")
    lines.append("  4. 只能动态时,加 `# pragma: allow-object <reason>` 并写清边界.")
    lines.append("  5. `scripts/` 与 `vendor/` 命中默认记为 whitelist,不作为门禁阻断.")

    if hits:
        lines.append("")
        lines.append("明细:")
        for hit in hits:
            rel = hit.path.relative_to(repo_root).as_posix()
            suffix = " reason={}".format(hit.allow_reason) if hit.allow_reason else ""
            lines.append(
                "  [{}] {}:{}:{} kind={} {}{}".format(
                    hit.status.upper(),
                    rel,
                    hit.line,
                    hit.col,
                    hit.kind,
                    hit.summary,
                    suffix,
                )
            )
    else:
        lines.append("")
        lines.append("未发现 `object` 类型标注.")

    return "\n".join(lines) + "\n"


def _render_json(*, repo_root: Path, hits: Sequence[_Hit]) -> str:
    payload = {
        "summary": {
            "total": len(hits),
            "block": sum(1 for hit in hits if hit.status == "block"),
            "allow": sum(1 for hit in hits if hit.status == "allow"),
            "whitelist": sum(1 for hit in hits if hit.status == "whitelist"),
            "by_kind": _count_by_kind(hits),
            "by_file": [{"path": rel, "count": count} for rel, count in _count_by_file(repo_root=repo_root, hits=hits)],
        },
        "hits": [
            {
                "path": hit.path.relative_to(repo_root).as_posix(),
                "line": hit.line,
                "col": hit.col,
                "end_line": hit.end_line,
                "end_col": hit.end_col,
                "kind": hit.kind,
                "summary": hit.summary,
                "status": hit.status,
                "allow_reason": hit.allow_reason,
            }
            for hit in hits
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描源码中的类型标注 `object` 使用.")
    parser.add_argument("paths", nargs="*", help="要扫描的路径(默认: `src/scalim` / `tests` / `scripts`).")
    parser.add_argument("--json", action="store_true", help="输出 JSON.")
    parser.add_argument("--report", default="", help="覆盖默认文本报告路径.")
    parser.add_argument("--no-artifacts", action="store_true", help="不自动写入 `.tmp/artifacts/object-type.report.{txt,json}`.")
    parser.add_argument("--check", action="store_true", help="若存在未 allow 的命中则返回非零退出码.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    rel_roots = tuple(Path(path) for path in args.paths) if args.paths else _DEFAULT_REL_ROOTS
    hits = scan_repo(repo_root=repo_root, rel_roots=rel_roots)

    text_report = _render_text_report(repo_root=repo_root, hits=hits)
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

    sys.stdout.write(output)

    if args.check and any(hit.status == "block" for hit in hits):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
