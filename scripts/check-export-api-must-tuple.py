#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "libcst>=1.8.0",
# ]
# ///
# ruff: noqa: T201
"""扫描并修复 `src/scalim/**.{py,pyi}` 中导出 API(`__all__`) 的 `list` 字面量用法.

约定:
- 若模块定义了 `__all__`,则必须使用 `tuple` 字面量:
  - ✅ `__all__ = ("foo", "bar")`
  - ✅ `__all__ = ()`
  - ❌ `__all__ = ["foo", "bar"]`
  - ❌ `__all__ = []`

增量治理:
- 由于历史存量较多, `--check` 默认使用允许名单(见 `--allow-file`) 防止“新增” `list` 用法.
- 要求全量清零时,使用 `--check --strict`.

用法:
    `uv run scripts/check-export-api-must-tuple.py --check`
    `uv run scripts/check-export-api-must-tuple.py --check --strict`
    `uv run scripts/check-export-api-must-tuple.py --fix`
    `uv run scripts/check-export-api-must-tuple.py --update-allow-file`

输出合约:
- `--check` 只控制退出码(发现 `list` 字面量时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import libcst as cst

_DEFAULT_ALLOW_FILE_REL = Path("scripts") / "check-export-api-must-tuple.allow.txt"


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    kind: str


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".pyi"}:
            continue
        yield path


def _collect_all_hits(path: Path, *, repo_root: Path) -> Tuple[List[_Hit], List[str]]:
    rel = path.relative_to(repo_root)
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(rel))
    except SyntaxError as exc:
        return [], ["{}: 语法错误(`SyntaxError`): {}".format(str(rel), exc)]

    hits: List[_Hit] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                continue
            if isinstance(node.value, ast.List):
                hits.append(_Hit(path=path, line=int(getattr(node, "lineno", 0) or 0), kind="list"))
        elif isinstance(node, ast.AnnAssign):
            if not (isinstance(node.target, ast.Name) and node.target.id == "__all__"):
                continue
            if isinstance(node.value, ast.List):
                hits.append(_Hit(path=path, line=int(getattr(node, "lineno", 0) or 0), kind="list"))
    return hits, []


def _list_to_tuple(node: cst.List) -> cst.Tuple:
    if not node.elements:
        return cst.Tuple(elements=())
    return cst.Tuple(
        elements=node.elements,
        lpar=[cst.LeftParen(whitespace_after=node.lbracket.whitespace_after)],
        rpar=[cst.RightParen(whitespace_before=node.rbracket.whitespace_before)],
    )


class _AllListToTupleTransformer(cst.CSTTransformer):
    def __init__(self) -> None:
        self.changed = False

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if not isinstance(updated_node.value, cst.List):
            return updated_node
        if not any(isinstance(t.target, cst.Name) and t.target.value == "__all__" for t in updated_node.targets):
            return updated_node
        self.changed = True
        new_value = _list_to_tuple(updated_node.value)
        return updated_node.with_changes(value=new_value)

    def leave_AnnAssign(self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign) -> cst.AnnAssign:
        if not isinstance(updated_node.value, cst.List):
            return updated_node
        if not (isinstance(updated_node.target, cst.Name) and updated_node.target.value == "__all__"):
            return updated_node
        self.changed = True
        new_value = _list_to_tuple(updated_node.value)
        return updated_node.with_changes(value=new_value)


def _fix_file(path: Path, *, repo_root: Path) -> Tuple[bool, Optional[str]]:
    rel = path.relative_to(repo_root)
    original = path.read_text(encoding="utf-8")
    try:
        module = cst.parse_module(original)
    except Exception as exc:  # pragma: no cover  # pragma: allow-no-cover libcst parse failure fallback
        return False, "{}: libcst 解析失败: {}".format(str(rel), exc)

    transformer = _AllListToTupleTransformer()
    updated = module.visit(transformer)
    if not transformer.changed:
        return False, None

    updated_text = updated.code
    if updated_text == original:
        return False, None

    path.write_text(updated_text, encoding="utf-8")
    return True, None


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="确保 `__all__` 使用 tuple 字面量(并支持自动修复).")
    p.add_argument("--root", default="src/scalim", help="扫描根目录(默认: src/scalim).")
    p.add_argument(
        "--allow-file",
        default=str(_DEFAULT_ALLOW_FILE_REL),
        help="允许名单文件路径(默认: scripts/check-export-api-must-tuple.allow.txt). 仅对 `--check` 生效.",
    )
    p.add_argument("--strict", action="store_true", help="严格模式: 不使用允许名单; 发现任意命中即失败.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="检查模式; 发现 `list` 字面量则失败.")
    g.add_argument("--fix", action="store_true", help="修复模式; 自动将 `__all__ = [...]` 改为 tuple.")
    g.add_argument("--update-allow-file", action="store_true", help="更新允许名单文件为当前命中集合(便于增量治理).")
    p.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    return p.parse_args(list(argv))


def _load_allow_file(path: Path) -> Tuple[set[str], List[str]]:
    if not path.exists():
        return set(), ["允许名单文件不存在: {}".format(str(path))]

    errors: List[str] = []
    allowed: set[str] = set()
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            errors.append("{}:{}: 不应以 '- ' 开头(只需写相对路径): {!r}".format(str(path), idx, raw))
            continue
        allowed.add(line)
    return allowed, errors


def _write_allow_file(path: Path, rel_paths: Sequence[str]) -> None:
    lines = [
        "# Generated by `scripts/check-export-api-must-tuple.py --update-allow-file`.",
        "# One path per line.",
        "",
    ]
    lines.extend(list(rel_paths))
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path.cwd().resolve()
    root = (repo_root / str(args.root)).resolve()
    if not root.exists():
        print("[错误] 根目录不存在: {}".format(root), file=sys.stderr)
        return 2

    failures: List[str] = []
    hits: List[_Hit] = []

    for path in sorted(_iter_python_files(root)):
        file_hits, file_errors = _collect_all_hits(path, repo_root=repo_root)
        hits.extend(file_hits)
        failures.extend(file_errors)

    if failures:
        print("[错误] 发现无法解析的文件 ({} 个):".format(len(failures)), file=sys.stderr)
        for line in failures:
            print("- {}".format(line), file=sys.stderr)
        return 2

    allow_file = (repo_root / str(args.allow_file)).resolve()
    hit_paths = sorted({str(h.path.relative_to(repo_root)) for h in hits})

    if args.update_allow_file:
        _write_allow_file(allow_file, hit_paths)
        print("[更新] 已写入允许名单 ({} 条): {}".format(len(hit_paths), str(allow_file.relative_to(repo_root))))
        return 0

    if args.check:
        allowed: set[str] = set()
        allow_errors: List[str] = []
        if not args.strict:
            allowed, allow_errors = _load_allow_file(allow_file)
            if allow_errors:
                print("[错误] 允许名单解析失败:", file=sys.stderr)
                for line in allow_errors:
                    print("- {}".format(line), file=sys.stderr)
                return 2

        unexpected = sorted(set(hit_paths) - allowed) if not args.strict else hit_paths
        if unexpected:
            print("[错误] 检测到 `__all__` 使用列表字面量 ({} 处):".format(len(unexpected)), file=sys.stderr)
            for hit in sorted(hits, key=lambda h: (str(h.path), h.line)):
                rel = str(hit.path.relative_to(repo_root))
                if rel not in unexpected:
                    continue
                print("- {}:{}".format(rel, hit.line), file=sys.stderr)
            print("\n修复: 运行 `uv run scripts/check-export-api-must-tuple.py --fix`", file=sys.stderr)
            if not args.strict:
                print("更新允许名单: 运行 `uv run scripts/check-export-api-must-tuple.py --update-allow-file`", file=sys.stderr)
            return 1

        if hit_paths and not args.strict:
            stale = sorted(allowed - set(hit_paths))
            msg = "[通过] 未新增 `__all__` 列表字面量 (历史存量 {} 个文件仍在允许名单).".format(len(hit_paths))
            if stale:
                msg += " (允许名单可收敛: {} 条已不再命中)".format(len(stale))
            if not args.quiet:
                print(msg)
            return 0

        if not args.quiet:
            print("[通过] 未发现 `__all__` 列表字面量 ({})".format(str(root)))
        return 0

    changed: List[Path] = []
    fix_failures: List[str] = []
    for path in sorted({hit.path for hit in hits}):
        did_change, err = _fix_file(path, repo_root=repo_root)
        if err:
            fix_failures.append(err)
            continue
        if did_change:
            changed.append(path)

    if fix_failures:
        print("[错误] 自动修复失败 ({} 个):".format(len(fix_failures)), file=sys.stderr)
        for line in fix_failures:
            print("- {}".format(line), file=sys.stderr)
        return 2

    if changed:
        print("[修复] 已更新 {} 个文件:".format(len(changed)))
        for path in changed:
            print("- {}".format(str(path.relative_to(repo_root))))
    else:
        print("[无变更] 未发现需要修复的文件.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
