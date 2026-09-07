# ruff: noqa: T201
"""
章节 `notebook` `cells-native` 机械检查（`live spec` `examples-marimo` `r1113`/`r1114` 静态门禁）.

规则（对应 `live spec` `examples-marimo` 的 `@req:r1113` / `@req:r1114`）:

- `r1113` 主路径委托: 章节 `notebook` 的 `cell` 内不得调用来自受限模块的
  模块级 `run_*()` 函数执行章节主路径（`run_chapter()` SSOT 入口豁免）.
  受限模块: `notebooks.*.support.*` / `scalim_misc.demo_*` / `scalim_misc.examples.*`.
  共享 `fixture` 装配（`build_*` 等）不在本规则范围（`r1111` 零件边界）.
- `r1114` 期望值可见: 章节调用 `make_chapter_result(details={<dict 字面量>})` 时,
  该字面量必须至少含一个 `expected` 前缀键;`details` 传入非字面量（变量/调用）时
  静态不可判定,不视为违规（人工复核兜底）.

白名单（文件级 `pragma`,同时豁免对应规则的报错）:
- `# pragma: allow-cells-native-run-delegation`  → 豁免 `r1113`
- `# pragma: allow-cells-native-expected-key`    → 豁免 `r1114`

扫描范围: `<root>/notebooks/marimo/**/ch*.py`（章节 `notebook` 命名约定,见 `r722`）.

用法:
- `uv run python scripts/check-notebook-cells-native.py --check`
- `uv run python scripts/check-notebook-cells-native.py --check --quiet`
- `uv run python scripts/check-notebook-cells-native.py --root /path/to/repo --check`

输出合约:
- `--check` 只控制退出码(有违规则非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 有违规时仍写 `stderr`.

退出码:
- 0: 通过
- 1: 发现违规(仅在 `--check` 时)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_PRAGMA_ALLOW_RUN = "pragma: allow-cells-native-run-delegation"
_PRAGMA_ALLOW_EXPECTED = "pragma: allow-cells-native-expected-key"
_NOTEBOOK_ROOT = Path("notebooks") / "marimo"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查章节 notebook cells-native gate (r1113/r1114).")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument("--check", action="store_true", help="发现违规时返回非 0 退出码.")
    parser.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    return parser.parse_args(argv)


def _is_restricted_module(module: str) -> bool:
    if module.startswith("notebooks.") and ".support." in module:
        return True
    return module == "scalim_misc" or module.startswith("scalim_misc.demo_") or module.startswith("scalim_misc.examples.")


def _collect_imports(tree: ast.AST) -> dict[str, str]:
    """局部名 -> 导入来源模块路径（仅统计 `from module import name` 与 `import module` 形态）."""
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports[alias.asname or alias.name] = module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name
    return imports


def _scan_run_delegation(path: Path, tree: ast.AST, *, repo_root: Path) -> list[str]:
    """`r1113`: 章节 `cell` 内调用受限模块的 `run_*()` 主路径委托."""
    imports = _collect_imports(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name == "run_chapter" or not name.startswith("run_"):
            continue
        module = imports.get(name)
        if module is None or not _is_restricted_module(module):
            continue
        rel_path = path.relative_to(repo_root)
        violations.append(
            "{}:{}: [r1113] cells 调用受限模块的 run_*(): {} (from {})".format(
                rel_path.as_posix(), getattr(node, "lineno", "?"), name, module
            )
        )
    return violations


def _scan_expected_key(path: Path, tree: ast.AST, *, repo_root: Path) -> list[str]:
    """`r1114`: `make_chapter_result(details=<dict 字面量>)` 必须含 `expected*` 键."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "make_chapter_result":
            continue
        details_arg = next((kw.value for kw in node.keywords if kw.arg == "details"), None)
        if not isinstance(details_arg, ast.Dict):
            continue
        keys = [kw.value for kw in details_arg.keys if isinstance(kw, ast.Constant) and isinstance(kw.value, str)]
        if any(str(key).startswith("expected") for key in keys):
            continue
        rel_path = path.relative_to(repo_root)
        violations.append(
            "{}:{}: [r1114] make_chapter_result(details={{...}}) 缺少 expected* 键".format(
                rel_path.as_posix(), getattr(node, "lineno", "?")
            )
        )
    return violations


def _scan_file(path: Path, *, repo_root: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    if _PRAGMA_ALLOW_RUN not in source:
        violations.extend(_scan_run_delegation(path, tree, repo_root=repo_root))
    if _PRAGMA_ALLOW_EXPECTED not in source:
        violations.extend(_scan_expected_key(path, tree, repo_root=repo_root))
    return violations


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()
    notebook_root = repo_root / _NOTEBOOK_ROOT
    if not notebook_root.is_dir():
        print("[错误] 未找到 `notebooks/marimo` 目录: {}".format(notebook_root), file=sys.stderr)
        return 1 if args.check else 0

    violations: list[str] = []
    for path in sorted(notebook_root.rglob("ch*.py")):
        if "__pycache__" in path.parts or ".tmp" in path.parts:
            continue
        violations.extend(_scan_file(path, repo_root=repo_root))

    if violations:
        print("[错误] `cells-native` 检查失败 ({} 处命中):".format(len(violations)), file=sys.stderr)
        for v in violations:
            print("- {}".format(v), file=sys.stderr)
        return 1 if args.check else 0

    if not args.quiet:
        print("[通过] `cells-native` 检查通过 (`r1113` `run_*` 委托 / `r1114` `expected*` 键)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
