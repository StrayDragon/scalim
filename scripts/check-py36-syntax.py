#!/usr/bin/env python
"""检查 `src/scalim/` 的 `Python 3.6` 语法兼容性(静态).

`CI`/开发环境可能没有 `Docker`,因此无法通过 `python:3.6` 容器执行 `compileall`.
本脚本用 `ast.parse(..., feature_version=(3, 6))` 做静态语法检查,用于兜底:

- 捕获 `Python 3.7+` 才支持的语法(例如赋值表达式 `:=`)
- 保持与运行时目标(`Python 3.6`)一致的语法门槛

注意:
- 这是“语法”层面的兼容性检查,不覆盖依赖解析或运行期行为差异。
"""

from __future__ import annotations

import ast
import sys
import tokenize
from pathlib import Path
from typing import List, Tuple


def _iter_py_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def main() -> int:
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

    print("通过: `src/scalim/` `Python 3.6` 语法兼容性检查通过 ({} 个文件)".format(len(py_files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
