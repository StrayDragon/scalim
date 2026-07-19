#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ruff: noqa: T201
# force-en
"""扫描源码中的 `cast(...)` 使用.

设计目标:
- 为 `cast` 治理建立可审阅基线,区分“需要静态化重构”与“确属必要的局部逃逸”.
- 允许对确属必要的例外做显式标记:
  - 行级: `# pragma: allow-cast <reason>`
  - 文件级: `# pragma: allow-cast-file <reason>`
- allow pragma 属于治理标记;在替代方案落地前不要直接删除.

用法:
    `uv run scripts/check-cast-usage.py`
    `uv run scripts/check-cast-usage.py --json`
    `uv run scripts/check-cast-usage.py --check`
    `uv run scripts/check-cast-usage.py --check --quiet`

输出合约:
- `--check` 只控制退出码(有 `block` 则非 0); 不隐含静默.
- `--quiet` 且无 `block` 时不写 `stdout`; 有 `block` 时仍写报告.
- `.tmp/artifacts/` 写入与 `--quiet` 正交(见 `--no-artifacts`).
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional, Sequence


_ALLOW_MARK = "pragma: allow-cast"
_ALLOW_FILE_MARK = "pragma: allow-cast-file"
_DEFAULT_REL_ROOTS = (Path("src") / "scalim", Path("tests"), Path("scripts"))
_DEFAULT_TEXT_REPORT_REL = Path(".tmp") / "artifacts" / "cast-usage.report.txt"
_DEFAULT_JSON_REPORT_REL = Path(".tmp") / "artifacts" / "cast-usage.report.json"
_CAST_MODULES = frozenset({"typing", "typing_extensions"})


@dataclass(frozen=True)
class _Binding:
    kind: str
    source: str


@dataclass
class _Scope:
    parent: Optional["_Scope"]
    bindings: dict[str, _Binding] = field(default_factory=dict)

    def bind(self, name: str, binding: _Binding) -> None:
        self.bindings[name] = binding

    def resolve(self, name: str) -> Optional[_Binding]:
        scope: Optional["_Scope"] = self
        while scope is not None:
            binding = scope.bindings.get(name)
            if binding is not None:
                return binding
            scope = scope.parent
        return None


@dataclass(frozen=True)
class _CommentPolicy:
    allow_lines: dict[int, str]
    allow_file_reason: str


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    col: int
    end_line: int
    end_col: int
    source_summary: str
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
    tail = text.split(marker, 1)[1].strip()
    return tail


def _parse_comment_policy(source: str) -> _CommentPolicy:
    allow_lines: dict[int, str] = {}
    allow_file_reason = ""
    in_header = True

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            stripped = token.string.lstrip("#").strip()
            if in_header and _ALLOW_FILE_MARK in stripped:
                reason = _reason_after_marker(stripped, _ALLOW_FILE_MARK)
                if reason:
                    allow_file_reason = reason
            if _ALLOW_MARK in stripped:
                reason = _reason_after_marker(stripped, _ALLOW_MARK)
                if reason:
                    allow_lines[int(token.start[0])] = reason
            continue

        if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.STRING and int(token.start[0]) == 1:
            continue
        in_header = False

    return _CommentPolicy(allow_lines=allow_lines, allow_file_reason=allow_file_reason)


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


def _extract_target_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    if isinstance(node, ast.Name):
        names.append(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for item in node.elts:
            names.extend(_extract_target_names(item))
    elif isinstance(node, ast.Starred):
        names.extend(_extract_target_names(node.value))
    return names


def _bind_assignment_targets(scope: _Scope, node: ast.AST) -> None:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    elif isinstance(node, ast.AugAssign):
        targets = [node.target]
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
    elif isinstance(node, ast.NamedExpr):
        targets = [node.target]

    for target in targets:
        for name in _extract_target_names(target):
            scope.bind(name, _Binding(kind="other", source="assignment"))

    if isinstance(node, ast.ExceptHandler) and node.name:
        scope.bind(str(node.name), _Binding(kind="other", source="except"))


def _bind_import(scope: _Scope, node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".")[0]
            if alias.name in _CAST_MODULES:
                scope.bind(local_name, _Binding(kind="module", source=alias.name))
            else:
                scope.bind(local_name, _Binding(kind="other", source="import"))
        return True

    if isinstance(node, ast.ImportFrom):
        module_name = node.module or ""
        for alias in node.names:
            local_name = alias.asname or alias.name
            if module_name in _CAST_MODULES and alias.name == "cast":
                scope.bind(local_name, _Binding(kind="cast", source="{}.cast".format(module_name)))
            else:
                scope.bind(local_name, _Binding(kind="other", source="import-from"))
        return True

    return False


def _bind_function_args(scope: _Scope, args: ast.arguments) -> None:
    for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
        scope.bind(arg.arg, _Binding(kind="other", source="arg"))
    if args.vararg is not None:
        scope.bind(args.vararg.arg, _Binding(kind="other", source="vararg"))
    if args.kwarg is not None:
        scope.bind(args.kwarg.arg, _Binding(kind="other", source="kwarg"))


class _ScopeBuilder:
    def __init__(self) -> None:
        self.scope_by_node: dict[ast.AST, _Scope] = {}

    def build(self, tree: ast.Module) -> dict[ast.AST, _Scope]:
        module_scope = _Scope(parent=None)
        self.scope_by_node[tree] = module_scope
        for stmt in tree.body:
            self._visit(stmt, module_scope)
        return self.scope_by_node

    def _visit(self, node: ast.AST, scope: _Scope) -> None:
        if _bind_import(scope, node):
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope.bind(node.name, _Binding(kind="other", source="function"))
            child = _Scope(parent=scope)
            self.scope_by_node[node] = child
            _bind_function_args(child, node.args)
            for stmt in node.body:
                self._visit(stmt, child)
            return

        if isinstance(node, ast.ClassDef):
            scope.bind(node.name, _Binding(kind="other", source="class"))
            child = _Scope(parent=scope)
            self.scope_by_node[node] = child
            for stmt in node.body:
                self._visit(stmt, child)
            return

        if isinstance(node, ast.Lambda):
            child = _Scope(parent=scope)
            self.scope_by_node[node] = child
            _bind_function_args(child, node.args)
            self._visit(node.body, child)
            return

        _bind_assignment_targets(scope, node)
        for child in ast.iter_child_nodes(node):
            self._visit(child, scope)


class _CastUsageScanner(ast.NodeVisitor):
    def __init__(self, *, path: Path, comment_policy: _CommentPolicy, scope_by_node: dict[ast.AST, _Scope], module_scope: _Scope) -> None:
        self._path = path
        self._comment_policy = comment_policy
        self._scope_by_node = scope_by_node
        self._current_scope = module_scope
        self.hits: list[_Hit] = []

    def _allow_reason_for(self, node: ast.Call) -> str:
        if self._comment_policy.allow_file_reason:
            return self._comment_policy.allow_file_reason
        start = int(getattr(node, "lineno", 0) or 0)
        end = _node_end_line(node)
        for line in range(start, end + 1):
            reason = self._comment_policy.allow_lines.get(line, "")
            if reason:
                return reason
        return ""

    def _resolve_source_summary(self, func: ast.AST) -> str:
        if isinstance(func, ast.Name):
            binding = self._current_scope.resolve(func.id)
            if binding is not None and binding.kind == "cast":
                return binding.source
            return ""

        if isinstance(func, ast.Attribute) and func.attr == "cast" and isinstance(func.value, ast.Name):
            binding = self._current_scope.resolve(func.value.id)
            if binding is not None and binding.kind == "module" and binding.source in _CAST_MODULES:
                return "{}.cast".format(binding.source)
        return ""

    def visit_Call(self, node: ast.Call) -> None:
        source_summary = self._resolve_source_summary(node.func)
        if source_summary:
            allow_reason = self._allow_reason_for(node)
            self.hits.append(
                _Hit(
                    path=self._path,
                    line=int(getattr(node, "lineno", 0) or 0),
                    col=int(getattr(node, "col_offset", 0) or 0) + 1,
                    end_line=_node_end_line(node),
                    end_col=_node_end_col(node),
                    source_summary=source_summary,
                    status="allow" if allow_reason else "block",
                    allow_reason=allow_reason,
                )
            )
        self.generic_visit(node)

    def generic_visit(self, node: ast.AST) -> None:
        next_scope = self._scope_by_node.get(node)
        if next_scope is not None:
            previous_scope = self._current_scope
            self._current_scope = next_scope
            super().generic_visit(node)
            self._current_scope = previous_scope
            return
        super().generic_visit(node)


def _scan_file(path: Path) -> list[_Hit]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.as_posix())
    comment_policy = _parse_comment_policy(source)
    scope_builder = _ScopeBuilder()
    scope_by_node = scope_builder.build(tree)
    module_scope = scope_by_node[tree]
    scanner = _CastUsageScanner(path=path, comment_policy=comment_policy, scope_by_node=scope_by_node, module_scope=module_scope)
    scanner.visit(tree)
    return sorted(scanner.hits, key=lambda item: (item.line, item.col, item.source_summary))


def scan_repo(*, repo_root: Path, rel_roots: Sequence[Path]) -> list[_Hit]:
    hits: list[_Hit] = []
    for path in _iter_python_files(repo_root=repo_root, rel_roots=rel_roots):
        hits.extend(_scan_file(path))
    return sorted(hits, key=lambda item: (str(item.path), item.line, item.col, item.source_summary))


def _count_by_source(hits: Sequence[_Hit], *, status: Optional[str] = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        if status is not None and hit.status != status:
            continue
        counts[hit.source_summary] = counts.get(hit.source_summary, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


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
        "cast 使用扫描报告",
        "",
        "摘要:",
        "  total={} block={} allow={}".format(total, blocked, allowed),
    ]

    source_counts = _count_by_source(hits)
    if source_counts:
        lines.append("  sources={}".format(", ".join("{}={}".format(name, count) for name, count in source_counts.items())))

    top_files = _count_by_file(repo_root=repo_root, hits=hits)
    if top_files:
        lines.extend(["", "热点文件(按总命中数排序):"])
        for rel, count in top_files[:20]:
            lines.append("  {} {}".format(str(count).rjust(3), rel))

    lines.extend(
        [
            "",
            "规避建议:",
            "  1. 返回值/参数已知时,收紧函数签名,不要再靠 `cast` 补类型.",
            "  2. 结构不透明时,优先补 dataclass / ABC / Protocol / TypedDict 等运行时契约.",
            "  3. 边界确实无法静态表达时,在调用行加 `# pragma: allow-cast <reason>`.",
            "  4. 文件整体承担兼容/框架职责时,在文件头注释区加 `# pragma: allow-cast-file <reason>`.",
            "  5. allow pragma 属于治理标记;未完成替代前不要直接删除.",
        ]
    )

    if hits:
        detail_hits = [hit for hit in hits if hit.status != "allow" or show_allow_details]
        if detail_hits:
            lines.extend(["", "明细:"])
            for hit in detail_hits:
                rel = hit.path.relative_to(repo_root).as_posix()
                suffix = " reason={}".format(hit.allow_reason) if hit.allow_reason else ""
                lines.append(
                    "  [{}] {}:{}:{} source={}{}".format(
                        hit.status.upper(),
                        rel,
                        hit.line,
                        hit.col,
                        hit.source_summary,
                        suffix,
                    )
                )
        if allowed and not show_allow_details:
            lines.extend(["", "allow 明细默认省略; 如需展开,运行 `uv run scripts/check-cast-usage.py --show-allow-details`."])
    else:
        lines.extend(["", "未发现 cast 使用."])

    return "\n".join(lines) + "\n"


def _render_json(*, repo_root: Path, hits: Sequence[_Hit]) -> str:
    payload = {
        "summary": {
            "total": len(hits),
            "block": sum(1 for hit in hits if hit.status == "block"),
            "allow": sum(1 for hit in hits if hit.status == "allow"),
            "by_source": _count_by_source(hits),
            "by_file": [{"path": rel, "count": count} for rel, count in _count_by_file(repo_root=repo_root, hits=hits)],
        },
        "hits": [
            {
                "path": hit.path.relative_to(repo_root).as_posix(),
                "line": hit.line,
                "col": hit.col,
                "end_line": hit.end_line,
                "end_col": hit.end_col,
                "source_summary": hit.source_summary,
                "status": hit.status,
                "allow_reason": hit.allow_reason,
            }
            for hit in hits
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描源码中的 `cast(...)` 使用.")
    parser.add_argument("paths", nargs="*", help="要扫描的路径(默认: `src/scalim` / `tests` / `scripts`).")
    parser.add_argument("--json", action="store_true", help="输出 JSON.")
    parser.add_argument("--report", default="", help="覆盖默认文本报告路径.")
    parser.add_argument("--no-artifacts", action="store_true", help="不自动写入 `.tmp/artifacts/cast-usage.report.{txt,json}`.")
    parser.add_argument("--check", action="store_true", help="若存在未 allow 的命中则返回非零退出码.")
    parser.add_argument("--quiet", action="store_true", help="静默模式: 无 block 时不向 stdout 写报告; 不影响 artifact.")
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

    has_blocks = any(hit.status == "block" for hit in hits)
    # `--quiet` 控制通过路径静默; `--check` 只控制退出码. 有 `block` 时始终写 `stdout`.
    if not (args.quiet and not has_blocks):
        sys.stdout.write(output)

    if args.check and has_blocks:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
