#!/usr/bin/env python3
"""检查第 1 层（`tier1`）公共接口入口的一致性.

检查项:
  - `tier1` 标记语法合法
  - 入口模块无重复
  - 标记指向的模块在 `src/` 下存在
  - 入口模块必须声明字面量 `__all__`（仅 `AST` 扫描；不 `import`）

`SSOT`:
  - `src/scalim/**/__init__.py` 标记:
      `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
  - 模块级 `__all__`（仅允许字符串常量组成的 `tuple`/`list`）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence

from public_api_tooling import (
    PublicApiProblem,
    discover_public_api_entrypoints,
    extract_literal_module_all,
    repo_root_for_script,
    resolve_module_source_path,
)


def _as_relpath(path: Path, *, repo_root: Path) -> str:
    return str(path.relative_to(repo_root)).replace("\\", "/")


def _format_problems(problems: Sequence[PublicApiProblem], *, repo_root: Path) -> str:
    lines: List[str] = []
    for p in problems:
        rel = _as_relpath(p.path, repo_root=repo_root) if p.path.exists() else str(p.path)
        module = str(p.module or "(unknown)")
        lines.append("- {}:{}: {}: {}".format(rel, int(p.lineno), module, p.reason))
    return "\n".join(lines)


def _collect_problems(repo_root: Path) -> Sequence[PublicApiProblem]:
    entrypoints, problems = discover_public_api_entrypoints(repo_root, tier=1)
    out: List[PublicApiProblem] = list(problems)

    for entry in entrypoints:
        module_path = resolve_module_source_path(repo_root, entry.module)
        if module_path is None:
            out.append(
                PublicApiProblem(
                    path=entry.marker_path,
                    lineno=entry.marker_lineno,
                    module=entry.module,
                    reason="在 `src/` 下找不到模块（期望存在 `src/{}.py` 或 `src/{}/__init__.py`）".format(
                        entry.module.replace(".", "/"),
                        entry.module.replace(".", "/"),
                    ),
                )
            )
            continue

        all_literal, err = extract_literal_module_all(module_path, repo_root=repo_root)
        if all_literal is None:
            out.append(
                PublicApiProblem(
                    path=entry.marker_path,
                    lineno=entry.marker_lineno,
                    module=entry.module,
                    reason="入口模块必须声明字面量 `__all__`（模块文件: {}）：{}".format(
                        _as_relpath(module_path, repo_root=repo_root),
                        str(err or "unknown error"),
                    ),
                )
            )
            continue

    return sorted(out, key=lambda p: (str(p.path), int(p.lineno), str(p.module), str(p.reason)))


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Tier 1 curated public API entrypoints consistency.")
    parser.add_argument("--check", action="store_true", help="Fail with non-zero exit code when problems are found.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = repo_root_for_script(Path(__file__))

    problems = list(_collect_problems(repo_root))
    if problems:
        sys.stderr.write("[错误] 第 1 层入口检查失败 ({} 个问题):\n".format(len(problems)))
        sys.stderr.write(_format_problems(problems, repo_root=repo_root))
        sys.stderr.write("\n")
        return 1 if args.check else 0

    sys.stdout.write("[通过] 第 1 层入口检查通过\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
