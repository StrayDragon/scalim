"""检查: 禁止 `runtime` 在 `src/scalim/` 中使用 `print(...)`.

用法:
- `uv run python scripts/check-no-print.py`
- `uv run python scripts/check-no-print.py --check`
- `uv run python scripts/check-no-print.py --check --quiet`

输出合约:
- `--check` 只控制退出码(发现 `print` 时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
- 非 `--check` 模式下 `--quiet` 跳过信息性报告.
"""

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class PrintCall:
    path: str
    line: int
    column: int


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if path.name == "__init__.py" and path.stat().st_size == 0:
            continue
        yield path


def _find_print_calls(path: Path) -> List[PrintCall]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return []

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        # 语法错误不在本 `gate` 覆盖范围内(由 `basedpyright` 与 `py36` 检查兜底).
        return []

    hits: List[PrintCall] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "print":
                line = int(getattr(node, "lineno", 0) or 0)
                col = int(getattr(node, "col_offset", 0) or 0)
                hits.append(PrintCall(path=str(path), line=line, column=col + 1))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return hits


def scan_print_calls(repo_root: Path) -> List[PrintCall]:
    root = repo_root / "src" / "scalim"
    rows: List[PrintCall] = []
    for path in _iter_py_files(root):
        rows.extend(_find_print_calls(path))
    rows.sort(key=lambda x: (x.path, x.line, x.column))
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="检查: 禁止 `runtime` 在 `src/scalim/` 中使用 `print(...)`.")
    p.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    p.add_argument("--check", action="store_true", help="发现 `print` 调用时直接失败.")
    p.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    args = p.parse_args(argv)

    repo_root = Path(str(args.root)).resolve()
    hits = scan_print_calls(repo_root)

    if not args.check:
        if not args.quiet:
            print("`print(...)` 使用扫描报告")
            print("")
            print("摘要: 总计={}".format(len(hits)))
            for hit in hits[:50]:
                print("  - {}:{}:{}".format(hit.path, hit.line, hit.column))
            if len(hits) > 50:
                print("  ... (还有 {} 条)".format(len(hits) - 50))
        return 0

    if hits:
        print(
            "[错误] 禁止在 `src/scalim/` 的 `runtime` 路径使用 `print(...)`; 请迁移到结构化日志(例如 `loggingx`).",
            file=sys.stderr,
        )
        for hit in hits[:50]:
            print("  - {}:{}:{}".format(hit.path, hit.line, hit.column), file=sys.stderr)
        if len(hits) > 50:
            print("  ... (还有 {} 条)".format(len(hits) - 50), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
