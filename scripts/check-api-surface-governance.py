#!/usr/bin/env python3
"""`src/scalim/` 的 `API` 表面治理检查脚本.

用于强制执行 `OpenSpec` `public-api-surface-governance` 的增量要求:
- `__all__` 不得导出非 `dunder` 的 `_...` 符号(例如 `_foo`).
- 内部实现模块必须显式封堵导出面:
  - 任意 `_internal/` 目录下的模块
  - 文件名以单个下划线开头的模块(例如 `_foo.py`)
  必须定义 `__all__`,且必须为空(`[]` 或 `()`).

输出合约:
- `--check` 只控制退出码(发现问题时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class AllAssignment:
    values: Optional[List[str]]
    is_empty_literal: bool
    kind: str


def _is_dunder(name: str) -> bool:
    s = str(name)
    return s.startswith("__") and s.endswith("__") and len(s) >= 4


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if path.is_file():
            yield path


def _is_internal_module_path(path: Path) -> bool:
    parts = tuple(path.parts)
    if "_internal" in parts:
        return True
    basename = path.name
    return basename.startswith("_") and not basename.startswith("__") and basename.endswith(".py")


def _extract_module_all(tree: ast.AST) -> Optional[AllAssignment]:
    last_value: Optional[ast.AST] = None
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                last_value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                last_value = node.value

    if last_value is None:
        return None

    if isinstance(last_value, ast.List):
        kind = "list"
        elts = list(last_value.elts)
    elif isinstance(last_value, ast.Tuple):
        kind = "tuple"
        elts = list(last_value.elts)
    else:
        return AllAssignment(values=None, is_empty_literal=False, kind=type(last_value).__name__)

    if not elts:
        return AllAssignment(values=[], is_empty_literal=True, kind=kind)

    values: List[str] = []
    for elt in elts:
        ast_str = getattr(ast, "Str", None)
        if ast_str is not None and isinstance(elt, ast_str):  # `py<3.8`: 新版运行时已移除
            values.append(str(getattr(elt, "s", "")))
            continue
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            values.append(str(elt.value))
            continue
        return AllAssignment(values=None, is_empty_literal=False, kind=kind)

    return AllAssignment(values=values, is_empty_literal=False, kind=kind)


def _check_file(path: Path, *, root: Path) -> List[str]:
    rel = str(path.relative_to(root))
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return ["{}: 语法错误(`SyntaxError`): {}".format(rel, exc)]

    all_assign = _extract_module_all(tree)

    errors: List[str] = []

    if all_assign is not None:
        if all_assign.values is None:
            errors.append("{}: `__all__` 必须是仅包含字符串字面量的列表/元组(当前: {})".format(rel, all_assign.kind))
        else:
            bad = sorted({name for name in all_assign.values if name.startswith("_") and not _is_dunder(name)})
            if bad:
                errors.append("{}: `__all__` 导出了内部下划线名称: {}".format(rel, ", ".join(bad)))

    if _is_internal_module_path(path):
        if all_assign is None:
            errors.append("{}: 内部模块必须定义 `__all__ = []`(或 `()`)".format(rel))
        elif not all_assign.is_empty_literal:
            errors.append("{}: 内部模块的 `__all__` 必须为空(当前: {})".format(rel, all_assign.kind))

    return errors


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 `src/scalim/` 的公共接口表面治理规则.")
    parser.add_argument(
        "--root",
        default="src/scalim",
        help="要扫描的根目录(默认: src/scalim).",
    )
    parser.add_argument("--check", action="store_true", help="执行检查; 发现问题时返回非 0 退出码.")
    parser.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(str(args.root)).resolve()
    if not root.exists():
        print("[错误] 根目录不存在: {}".format(root), file=sys.stderr)
        return 2

    failures: List[str] = []
    for path in sorted(_iter_python_files(root)):
        failures.extend(_check_file(path, root=root))

    if failures:
        print("[错误] 公共接口表面治理检查失败 ({} 个问题):".format(len(failures)), file=sys.stderr)
        for line in failures:
            print("- {}".format(line), file=sys.stderr)
        return 1

    if not args.quiet:
        print("[通过] 公共接口表面治理检查通过 ({})".format(str(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
