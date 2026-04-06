# ruff: noqa: T201
"""
检查 `pytest` `monkeypatch` 的禁止模式(静态门禁).

当前规则:
- 禁止通过 `monkeypatch.setattr(..., \"_private\", ...)` 改写私有名称
- 禁止改写全局 `import` 机制:
  - `monkeypatch.setattr(builtins, \"__import__\", ...)`
  - `monkeypatch.setattr(importlib, \"import_module\", ...)`

该脚本只扫描 `tests/**.py`,不执行运行时模块的 `import`.

用法:
- `uv run python scripts/check-monkeypatch-policy.py --check`
- `uv run python scripts/check-monkeypatch-policy.py --root /path/to/repo --check`

退出码:
- 0: 通过
- 1: 发现违规(仅在 `--check` 时)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 monkeypatch policy gate.")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument("--check", action="store_true", help="发现违规时返回非 0 退出码.")
    return parser.parse_args(argv)


def _scan_file(path: Path, *, repo_root: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue

        # 仅对 `pytest` 的 `monkeypatch` 夹具施加规则(避免误伤其它同名变量).
        if not (isinstance(func.value, ast.Name) and func.value.id == "monkeypatch" and func.attr == "setattr"):
            continue

        if len(node.args) < 2:
            continue

        target_expr = node.args[0]
        name_expr = node.args[1]

        if not (isinstance(name_expr, ast.Constant) and isinstance(name_expr.value, str)):
            continue

        attr_name = str(name_expr.value)

        rel_path = path.relative_to(repo_root)
        lineno = getattr(node, "lineno", "?")
        loc = "{}:{}".format(rel_path.as_posix(), lineno)

        if attr_name.startswith("_"):
            violations.append("{}: monkeypatch.setattr(..., {!r}, ...) patches a private name".format(loc, attr_name))
            continue

        if attr_name == "__import__" and isinstance(target_expr, ast.Name) and target_expr.id == "builtins":
            violations.append("{}: monkeypatch.setattr(builtins, '__import__', ...) patches global import".format(loc))
            continue

        if attr_name == "import_module" and isinstance(target_expr, ast.Name) and target_expr.id == "importlib":
            violations.append("{}: monkeypatch.setattr(importlib, 'import_module', ...) patches global import".format(loc))
            continue

    return violations


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        print("[错误] 未找到 `tests/` 目录: {}".format(tests_dir), file=sys.stderr)
        return 1 if args.check else 0

    violations: list[str] = []
    for path in sorted(tests_dir.rglob("*.py")):
        violations.extend(_scan_file(path, repo_root=repo_root))

    if violations:
        print("[错误] `monkeypatch` 政策检查失败 ({} 处命中):".format(len(violations)), file=sys.stderr)
        for v in violations:
            print("- {}".format(v), file=sys.stderr)
        return 1 if args.check else 0

    print("[通过] `monkeypatch` 政策检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
