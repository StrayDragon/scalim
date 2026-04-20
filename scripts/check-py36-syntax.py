#!/usr/bin/env python
"""检查 `src/scalim/` 的 `Python 3.6` 语法兼容性(静态).

本脚本用 `ast.parse(..., feature_version=(3, 6))` 做静态语法检查:

- 捕获 `Python 3.7+` 才支持的语法(例如赋值表达式 `:=`)
- 保持与运行时目标(`Python 3.6`)一致的语法门槛

可选:
- `--public-api-import-smoke`: 基于自动生成的 `.tmp/public_api_jump_imports.py` 对 Tier 1 public API 做 import smoke,
  并额外验证生成物本身也符合 `Python 3.6` 语法；生成物缺失时会自动生成。

注意:
- 这是“语法”层面的兼容性检查,不覆盖依赖解析或运行期行为差异。
"""

from __future__ import annotations

import argparse
import ast
import importlib
import sys
import tokenize
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import List, Sequence, Tuple


def _iter_py_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Python 3.6 syntax compatibility for `src/scalim/`.")
    parser.add_argument(
        "--public-api-import-smoke",
        action="store_true",
        help="Also smoke-test Tier 1 public API imports via `.tmp/public_api_jump_imports.py` (auto-generated when missing).",
    )
    parser.add_argument(
        "--regen-public-api-jump-imports",
        action="store_true",
        help="Regenerate `.tmp/public_api_jump_imports.py` before running the smoke test.",
    )
    return parser.parse_args(list(argv))


def _ensure_public_api_jump_imports(repo_root: Path, *, regen: bool) -> Path:
    out_path = repo_root / ".tmp" / "public_api_jump_imports.py"
    if out_path.exists() and not regen:
        return out_path

    gen_script = repo_root / "scripts" / "gen-public-api-jump-imports.py"
    try:
        run([sys.executable, str(gen_script)], cwd=str(repo_root), check=True)
    except CalledProcessError as exc:
        raise RuntimeError("生成 `.tmp/public_api_jump_imports.py` 失败: {}".format(exc)) from exc

    if not out_path.exists():
        raise RuntimeError("生成脚本执行成功但未找到产物: {}".format(out_path))
    return out_path


def _run_public_api_import_smoke(repo_root: Path, jump_imports_path: Path) -> None:
    src_root = repo_root / "src"
    tmp_root = jump_imports_path.parent

    try:
        with tokenize.open(str(jump_imports_path)) as handle:
            jump_text = handle.read()
        ast.parse(jump_text, filename=str(jump_imports_path), feature_version=(3, 6))
    except SyntaxError as exc:
        raise RuntimeError(
            "生成物语法不兼容 Python 3.6: {}:{}: {}".format(
                jump_imports_path,
                getattr(exc, "lineno", "?"),
                getattr(exc, "msg", str(exc)),
            )
        ) from exc

    sys.path.insert(0, str(tmp_root))
    sys.path.insert(0, str(src_root))
    try:
        sys.modules.pop("public_api_jump_imports", None)
        jump_mod = importlib.import_module("public_api_jump_imports")
    except BaseException as exc:
        raise RuntimeError("导入失败: public_api_jump_imports (path={})".format(jump_imports_path)) from exc

    run_all = getattr(jump_mod, "run_all", None)
    if run_all is None or not callable(run_all):
        raise RuntimeError("生成物缺少可调用的 `run_all()` (path={})".format(jump_imports_path))

    run_all()


def main() -> int:
    args = _parse_args(sys.argv[1:])
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src" / "scalim"
    if not src_root.exists():
        print("[错误] 未找到目录: {}".format(src_root), file=sys.stderr)
        return 2

    py_files = _iter_py_files(src_root)
    failures: List[Tuple[Path, SyntaxError]] = []
    for path in py_files:
        try:
            with tokenize.open(str(path)) as f:
                text = f.read()
            ast.parse(text, filename=str(path), feature_version=(3, 6))
        except SyntaxError as exc:
            failures.append((path, exc))

    if failures:
        print("[错误] 检测到不兼容 `Python 3.6` 的语法:", file=sys.stderr)
        for path, exc in failures[:20]:
            location = "{}:{}".format(path, getattr(exc, "lineno", "?"))
            detail = getattr(exc, "msg", str(exc))
            print("  - {}: {}".format(location, detail), file=sys.stderr)
        if len(failures) > 20:
            print("  ... (其余 {} 处省略)".format(len(failures) - 20), file=sys.stderr)
        return 1

    if args.public_api_import_smoke:
        try:
            jump_imports_path = _ensure_public_api_jump_imports(
                repo_root,
                regen=bool(args.regen_public_api_jump_imports),
            )
            _run_public_api_import_smoke(repo_root, jump_imports_path)
        except BaseException as exc:
            print("[错误] Tier 1 public API import smoke 失败: {}".format(exc), file=sys.stderr)
            return 1
        print("通过: Tier 1 public API import smoke (`{}`)".format(jump_imports_path))

    print("通过: `src/scalim/` `Python 3.6` 语法兼容性检查通过 ({} 个文件)".format(len(py_files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
