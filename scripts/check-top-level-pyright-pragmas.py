#!/usr/bin/env python3
# NOTE: 继续按模块簇清理下一批顶层 `# pyright:`，并统一收口运行时契约规则检查

from __future__ import annotations

import argparse
import ast
import io
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

DEFAULT_MANIFEST = "scripts/top-level-pyright-pragmas.txt"


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查 `src/scalim/` 运行时契约规则(`pyright` 顶层指令 + 类内 `if TYPE_CHECKING:` 条件方法)"
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help="允许清单文件路径，默认 `scripts/top-level-pyright-pragmas.txt`",
    )
    parser.add_argument(
        "--strict-top-level",
        action="store_true",
        help="启用严格顶层规则：若 `# pyright:` 未出现在真实文件头注释区则直接报错",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="用当前源码扫描结果覆盖清单文件",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式: 仅错误/警告输出到 stderr, 通过时不输出",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


@dataclass(frozen=True)
class _PragmaLocation:
    line: int
    column: int


@dataclass(frozen=True)
class _ConditionalMethodLocation:
    line: int
    column: int
    class_name: str
    method_name: str


def _is_pyright_pragma(text: str) -> bool:
    return text.lstrip().startswith("# pyright:")


def _is_standalone_comment(token: tokenize.TokenInfo) -> bool:
    return token.line[: token.start[1]].strip() == ""


def _scan_pyright_pragmas_in_file(path: Path) -> Tuple[bool, List[_PragmaLocation]]:
    text = path.read_text(encoding="utf-8")
    top_level_found = False
    misplaced: List[_PragmaLocation] = []
    seen_non_header_token = False

    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                if not _is_standalone_comment(token):
                    continue
                if not _is_pyright_pragma(token.string):
                    continue
                line, column = token.start
                if not seen_non_header_token and column == 0:
                    top_level_found = True
                    continue
                misplaced.append(_PragmaLocation(line=line, column=column))
                continue
            if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.DEDENT, tokenize.ENDMARKER):
                continue
            seen_non_header_token = True
    except tokenize.TokenError as exc:
        raise ValueError("扫描 `{}` 时 `tokenize` 失败: {}".format(path.as_posix(), exc))

    return top_level_found, misplaced


def _scan_top_level_pyright_files(repo_root: Path) -> Tuple[Set[str], Dict[str, List[_PragmaLocation]]]:
    src_root = repo_root / "src" / "scalim"
    found: Set[str] = set()
    misplaced: Dict[str, List[_PragmaLocation]] = {}

    for path in src_root.rglob("*.py"):
        has_top_level, file_misplaced = _scan_pyright_pragmas_in_file(path)
        rel = path.relative_to(repo_root).as_posix()
        if has_top_level:
            found.add(rel)
        if file_misplaced:
            misplaced[rel] = file_misplaced
    return found, misplaced


def _is_type_checking_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    return False


def _scan_class_body_for_conditional_methods(
    nodes: Sequence[ast.stmt],
    *,
    class_stack: Sequence[str],
    inside_type_checking: bool,
    violations: List[_ConditionalMethodLocation],
) -> None:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if inside_type_checking:
                violations.append(
                    _ConditionalMethodLocation(
                        line=node.lineno,
                        column=node.col_offset,
                        class_name=".".join(class_stack),
                        method_name=node.name,
                    )
                )
            continue

        if isinstance(node, ast.If):
            _scan_class_body_for_conditional_methods(
                node.body,
                class_stack=class_stack,
                inside_type_checking=inside_type_checking or _is_type_checking_expr(node.test),
                violations=violations,
            )
            _scan_class_body_for_conditional_methods(
                node.orelse,
                class_stack=class_stack,
                inside_type_checking=inside_type_checking,
                violations=violations,
            )
            continue

        if isinstance(node, ast.ClassDef):
            _scan_class_body_for_conditional_methods(
                node.body,
                class_stack=tuple(class_stack) + (node.name,),
                inside_type_checking=inside_type_checking,
                violations=violations,
            )


def _scan_type_checking_class_methods_in_file(path: Path) -> List[_ConditionalMethodLocation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.as_posix())
    violations: List[_ConditionalMethodLocation] = []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        _scan_class_body_for_conditional_methods(
            node.body,
            class_stack=(node.name,),
            inside_type_checking=False,
            violations=violations,
        )

    return violations


def _scan_type_checking_class_methods(repo_root: Path) -> Dict[str, List[_ConditionalMethodLocation]]:
    src_root = repo_root / "src" / "scalim"
    violations: Dict[str, List[_ConditionalMethodLocation]] = {}

    for path in src_root.rglob("*.py"):
        file_violations = _scan_type_checking_class_methods_in_file(path)
        if file_violations:
            rel = path.relative_to(repo_root).as_posix()
            violations[rel] = file_violations
    return violations


def _format_misplaced(misplaced: Dict[str, List[_PragmaLocation]]) -> List[str]:
    lines: List[str] = []
    for rel in sorted(misplaced):
        for location in misplaced[rel]:
            lines.append("{}:{}:{}".format(rel, location.line, location.column + 1))
    return lines


def _report_misplaced(misplaced: Dict[str, List[_PragmaLocation]]) -> None:
    if not misplaced:
        return
    print("[错误] 发现不符合严格顶层规则的 `# pyright:` 指令:", file=sys.stderr)
    for item in _format_misplaced(misplaced):
        print("  - {}".format(item), file=sys.stderr)
    print("[提示] `# pyright:` 只能位于真实文件头注释区(在首个代码/模块 `docstring`/`import` 之前,且列号必须为 1)", file=sys.stderr)


def _format_conditional_methods(violations: Dict[str, List[_ConditionalMethodLocation]]) -> List[str]:
    lines: List[str] = []
    for rel in sorted(violations):
        for location in violations[rel]:
            lines.append(
                "{}:{}:{}  类={} 方法={}".format(
                    rel,
                    location.line,
                    location.column + 1,
                    location.class_name,
                    location.method_name,
                )
            )
    return lines


def _report_conditional_methods(violations: Dict[str, List[_ConditionalMethodLocation]]) -> None:
    if not violations:
        return
    print("[错误] 发现类内 `if TYPE_CHECKING:` 条件方法，违反运行时契约规则:", file=sys.stderr)
    for item in _format_conditional_methods(violations):
        print("  - {}".format(item), file=sys.stderr)
    print("[提示] 请改为显式运行时契约，例如 `ABC` + `@abstractmethod`。", file=sys.stderr)


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

    found, misplaced = _scan_top_level_pyright_files(repo_root)
    conditional_methods = _scan_type_checking_class_methods(repo_root)

    has_errors = False

    if conditional_methods:
        _report_conditional_methods(conditional_methods)
        has_errors = True

    if args.strict_top_level and misplaced:
        _report_misplaced(misplaced)
        has_errors = True

    if has_errors:
        if not args.sync:
            print(
                "[提示] 清理这些运行时契约违规项后，再按需执行 `python scripts/check-top-level-pyright-pragmas.py --sync`", file=sys.stderr
            )
        return 1

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
        if not args.quiet:
            if args.strict_top_level:
                print("检查通过: 顶层 `# pyright:` 指令未新增, 严格顶层规则通过, 未发现类内 `if TYPE_CHECKING:` 条件方法, 清单已同步")
            else:
                print("检查通过: 顶层 `# pyright:` 指令未新增, 未发现类内 `if TYPE_CHECKING:` 条件方法, 清单已同步")
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
