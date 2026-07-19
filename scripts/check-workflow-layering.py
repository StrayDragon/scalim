# ruff: noqa: T201
# force-en
"""
检查 `workflow` 分层治理约束:

- `src/scalim/workflow/**` MUST NOT `import`/动态 `import` `scalim.dsl.*`
- `src/scalim/dsl/yaml_dsl/runtime/**` MUST NOT 包含 `workflow_*.py`

该脚本是静态门禁:只依赖文件系统与 AST,不执行运行时模块的 `import`.
失败属于严重架构违规: quiet 不得吞掉失败报告.

用法:
- `uv run python scripts/check-workflow-layering.py --check`
- `uv run python scripts/check-workflow-layering.py --check --quiet`
- `uv run python scripts/check-workflow-layering.py --root /path/to/repo --check`

输出合约:
- `--check` 只控制退出码(有违规则非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 有违规时仍写 `stderr`(严重错误不可静默).

退出码:
- 0: 通过
- 1: 发现违规(仅在 `--check` 时)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _iter_py_files(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts])


def _is_importing_dsl(module: str | None, *, is_relative: bool) -> bool:
    if not module:
        return False
    if not is_relative:
        return module == "scalim.dsl" or module.startswith("scalim.dsl.")
    # `scalim.workflow.*` 内的相对导入不得越界到 `scalim.dsl.*`.
    return module.split(".")[0] == "dsl"


def _extract_import_dsl_violations(src: str, *, file_path: Path, repo_root: Path) -> list[str]:
    tree = ast.parse(src, filename=str(file_path))
    rel = file_path.relative_to(repo_root).as_posix()

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_importing_dsl(alias.name, is_relative=False):
                    violations.append("{}:{}: import {!r}".format(rel, int(node.lineno), alias.name))

        if isinstance(node, ast.ImportFrom):
            is_relative = bool(node.level)
            module = node.module
            if _is_importing_dsl(module, is_relative=is_relative):
                violations.append("{}:{}: from {}{!r} import ...".format(rel, int(node.lineno), "." * int(node.level), module))

        if isinstance(node, ast.Call):
            func = node.func
            func_name = None
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr

            if func_name not in {"__import__", "import_module"}:
                continue

            if not node.args:
                continue

            arg0 = node.args[0]
            if not isinstance(arg0, ast.Constant) or not isinstance(arg0.value, str):
                continue

            mod = str(arg0.value)
            if mod == "scalim.dsl" or mod.startswith("scalim.dsl."):
                violations.append("{}:{}: dynamic import {!r} via {}".format(rel, int(node.lineno), mod, func_name))

    return violations


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 workflow layering gate.")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument("--check", action="store_true", help="发现违规时返回非 0 退出码.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式: 通过时不向 stdout 写报告; 违规仍写 stderr.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()

    workflow_root = repo_root / "src" / "scalim" / "workflow"
    runtime_root = repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "runtime"

    if not workflow_root.is_dir():
        # 配置/路径错误同样视为严重失败信号, quiet 不得吞掉.
        print("[错误] 未找到工作流目录: {}".format(workflow_root), file=sys.stderr)
        return 1 if args.check else 0

    violations: list[str] = []
    for p in _iter_py_files(workflow_root):
        src = p.read_text(encoding="utf-8")
        violations.extend(_extract_import_dsl_violations(src, file_path=p, repo_root=repo_root))

    workflow_runtime_files: list[str] = []
    if runtime_root.is_dir():
        workflow_runtime_files = sorted([p.relative_to(runtime_root).as_posix() for p in runtime_root.rglob("workflow_*.py")])

    if violations or workflow_runtime_files:
        # 严重错误: 始终写 stderr(不受 --quiet 影响).
        print("[错误] 工作流分层检查失败:", file=sys.stderr)
        if violations:
            print("- 工作流层不得导入 DSL 模块:", file=sys.stderr)
            for v in violations:
                print("  - {}".format(v), file=sys.stderr)

        if workflow_runtime_files:
            print("- `yaml_dsl/runtime` 下不得包含 `workflow_*.py`:", file=sys.stderr)
            for rel in workflow_runtime_files:
                print("  - {}".format(rel), file=sys.stderr)

        return 1 if args.check else 0

    if not args.quiet:
        print("[通过] 工作流分层检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
