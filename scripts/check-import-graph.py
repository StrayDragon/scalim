# ruff: noqa: T201
# force-en
"""
检查主包(`src/scalim/`)导入结构:

- 导入图无环(排除 `src/scalim/vendor/**`)
- 主包禁止函数内导入(排除 `vendor`)

该脚本是静态门禁:只依赖文件系统与 AST,不执行运行时模块的 `import`.
失败属于严重架构违规: `quiet` 不得吞掉失败报告.

用法:
- `uv run python scripts/check-import-graph.py --check`
- `uv run python scripts/check-import-graph.py --check --quiet`
- `uv run python scripts/check-import-graph.py --root /path/to/repo --check`

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
from collections import deque
from pathlib import Path
from typing import Iterable


def _iter_py_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*.py"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        paths.append(path)
    return sorted(paths)


def _is_vendor_file(path: Path, *, scalim_root: Path) -> bool:
    try:
        rel = path.relative_to(scalim_root)
    except ValueError:
        return False
    return "vendor" in rel.parts


def _module_name_for_path(path: Path, *, src_root: Path) -> str:
    rel = path.relative_to(src_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _resolve_relative_import(
    *,
    current_module: str,
    current_is_package: bool,
    level: int,
    module: str | None,
) -> str | None:
    cur_parts = current_module.split(".")
    pkg_parts = cur_parts if current_is_package else cur_parts[:-1]

    # PEP 328: `level=1` 表示当前包; `level=2` 表示父包,以此类推.
    up = level - 1
    if up > len(pkg_parts):
        return None

    base_parts = pkg_parts[: len(pkg_parts) - up]
    if module:
        base_parts += module.split(".")
    if not base_parts:
        return None
    return ".".join(base_parts)


def _tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph.get(v, set()):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in sorted(graph):
        if v not in indices:
            strongconnect(v)

    return sccs


def _shortest_cycle_from_start(graph: dict[str, set[str]], *, component: set[str], start: str) -> list[str]:
    """
    返回从 `start` 出发回到 `start` 的最短环(包含首尾重复 `start`).
    若未找到则返回空列表.
    """

    q: deque[str] = deque()
    pred: dict[str, str] = {}
    dist: dict[str, int] = {}
    seen: set[str] = set()

    for nxt in sorted(graph.get(start, set())):
        if nxt not in component:
            continue
        if nxt == start:
            # 自环不作为导入环回归护栏(主要关注 2+ 节点的真实循环依赖).
            continue
        pred[nxt] = start
        dist[nxt] = 1
        seen.add(nxt)
        q.append(nxt)

    while q:
        cur = q.popleft()
        for nxt in graph.get(cur, set()):
            if nxt not in component:
                continue
            if nxt == start:
                # 重建路径: `start -> ... -> cur -> start`
                chain: list[str] = [cur]
                while chain[-1] != start:
                    chain.append(pred[chain[-1]])
                chain.reverse()
                chain.append(start)
                return chain
            if nxt in seen:
                continue
            seen.add(nxt)
            pred[nxt] = cur
            dist[nxt] = dist[cur] + 1
            q.append(nxt)

    return []


def _shortest_cycle_in_component(graph: dict[str, set[str]], component: set[str]) -> list[str]:
    best: list[str] = []
    for start in sorted(component):
        cycle = _shortest_cycle_from_start(graph, component=component, start=start)
        if not cycle:
            continue
        if not best or len(cycle) < len(best):
            best = cycle
    return best


def _collect_function_local_imports(py_files: Iterable[Path], *, scalim_root: Path) -> list[str]:
    violations: list[str] = []
    for file_path in py_files:
        if _is_vendor_file(file_path, scalim_root=scalim_root):
            continue
        rel_file = file_path.relative_to(scalim_root.parents[1]).as_posix()

        src = file_path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(file_path))

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self._func_stack: list[ast.AST] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - ast naming
                self._func_stack.append(node)
                self.generic_visit(node)
                self._func_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802 - ast naming
                self._func_stack.append(node)
                self.generic_visit(node)
                self._func_stack.pop()

            def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 - ast naming
                if not self._func_stack:
                    return
                fn_name = getattr(self._func_stack[-1], "name", "<function>")
                for alias in node.names:
                    violations.append("{}:{}: import {!r} inside {}".format(rel_file, int(node.lineno), alias.name, fn_name))

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802 - ast naming
                if not self._func_stack:
                    return
                fn_name = getattr(self._func_stack[-1], "name", "<function>")
                mod = node.module or ""
                for alias in node.names:
                    dotted = "{}{}".format("." * int(getattr(node, "level", 0)), mod)
                    violations.append(
                        "{}:{}: from {} import {!r} inside {}".format(rel_file, int(node.lineno), dotted, alias.name, fn_name)
                    )

        Visitor().visit(tree)

    return violations


def _build_import_graph(
    py_files: Iterable[Path],
    *,
    src_root: Path,
    scalim_root: Path,
) -> tuple[dict[str, set[str]], dict[str, Path]]:
    module_for_path: dict[Path, str] = {}
    path_for_module: dict[str, Path] = {}

    for p in py_files:
        if _is_vendor_file(p, scalim_root=scalim_root):
            continue
        mod = _module_name_for_path(p, src_root=src_root)
        module_for_path[p] = mod
        path_for_module[mod] = p

    graph: dict[str, set[str]] = {m: set() for m in path_for_module}

    for file_path, current_module in module_for_path.items():
        src = file_path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(file_path))
        current_is_package = file_path.name == "__init__.py"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name in path_for_module:
                        graph[current_module].add(name)
                continue

            if not isinstance(node, ast.ImportFrom):
                continue

            if node.level:
                resolved = _resolve_relative_import(
                    current_module=current_module,
                    current_is_package=current_is_package,
                    level=int(node.level),
                    module=node.module,
                )
            else:
                resolved = node.module

            if not resolved:
                continue

            # `from X import Y` 至少依赖 `X`
            if resolved in path_for_module:
                graph[current_module].add(resolved)

            # 启发式: 如果 `Y` 是 `X` 下的子模块,则也记录一条 `X.Y` 的直接边
            for alias in node.names:
                candidate = "{}.{}".format(resolved, alias.name)
                if candidate in path_for_module:
                    graph[current_module].add(candidate)

    # 防御式处理: 仅保留图中已知节点的边,避免误扫第三方/外部依赖.
    for src_mod, deps in list(graph.items()):
        graph[src_mod] = {dep for dep in deps if dep in graph}

    return graph, path_for_module


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查主包导入图无环 + 禁止函数内导入.")
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
    src_root = repo_root / "src"
    scalim_root = src_root / "scalim"

    if not scalim_root.is_dir():
        # 配置/路径错误同样视为严重失败信号, `quiet` 不得吞掉.
        print("[错误] 未找到主包目录: {}".format(scalim_root), file=sys.stderr)
        return 1 if args.check else 0

    py_files = _iter_py_files(scalim_root)

    graph, path_for_module = _build_import_graph(py_files, src_root=src_root, scalim_root=scalim_root)
    sccs = _tarjan_scc(graph)
    cyclic_components = [set(comp) for comp in sccs if len(comp) > 1]

    cycles: list[list[str]] = []
    for comp in cyclic_components:
        cycle = _shortest_cycle_in_component(graph, comp)
        if cycle:
            cycles.append(cycle)

    local_imports = _collect_function_local_imports(py_files, scalim_root=scalim_root)

    if cycles or local_imports:
        # 严重错误: 始终写 `stderr`(不受 `--quiet` 影响).
        print("[错误] 主包导入结构检查失败:", file=sys.stderr)
        if cycles:
            print("- 导入图存在 {} 个循环依赖:".format(len(cycles)), file=sys.stderr)
            for cycle in cycles:
                chain = " -> ".join(cycle)
                print("  - 导入环(长度={}): {}".format(len(cycle) - 1, chain), file=sys.stderr)
                for mod in sorted(set(cycle)):
                    path = path_for_module.get(mod)
                    if path is None:
                        continue
                    rel = path.relative_to(repo_root).as_posix()
                    print("      {} = {}".format(mod, rel), file=sys.stderr)

        if local_imports:
            print("- 发现函数内导入(禁止):", file=sys.stderr)
            for v in local_imports:
                print("  - {}".format(v), file=sys.stderr)

        return 1 if args.check else 0

    if not args.quiet:
        print("[通过] 主包导入结构检查通过 (模块数={})".format(len(graph)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
