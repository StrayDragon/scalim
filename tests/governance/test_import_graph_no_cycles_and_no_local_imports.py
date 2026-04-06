import ast
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from tests.support.pathing import repo_root as _repo_root


def _iter_py_files(root: Path) -> List[Path]:
    return sorted([p for p in root.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts])


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
    module: Optional[str],
) -> Optional[str]:
    cur_parts = current_module.split(".")
    pkg_parts = cur_parts if current_is_package else cur_parts[:-1]

    # PEP 328: level=1 means current package; level=2 means parent, etc.
    up = level - 1
    if up > len(pkg_parts):
        return None

    base_parts = pkg_parts[: len(pkg_parts) - up]
    if module:
        base_parts += module.split(".")
    if not base_parts:
        return None
    return ".".join(base_parts)


def _tarjan_scc(graph: Dict[str, Set[str]]) -> List[List[str]]:
    index = 0
    stack: List[str] = []
    on_stack: Set[str] = set()
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    sccs: List[List[str]] = []

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
            comp: List[str] = []
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


def _collect_function_local_imports(py_files: Iterable[Path], *, scalim_root: Path) -> List[str]:
    violations: List[str] = []
    for file_path in py_files:
        rel_parts = file_path.relative_to(scalim_root).parts
        if "vendor" in rel_parts:
            continue

        src = file_path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(file_path))

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self._func_stack: List[ast.AST] = []

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
                    violations.append("{}:{}: import {!r} inside {}".format(file_path, int(node.lineno), alias.name, fn_name))

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802 - ast naming
                if not self._func_stack:
                    return
                fn_name = getattr(self._func_stack[-1], "name", "<function>")
                mod = node.module or ""
                for alias in node.names:
                    dotted = "{}{}".format("." * int(getattr(node, "level", 0)), mod)
                    violations.append(
                        "{}:{}: from {} import {!r} inside {}".format(file_path, int(node.lineno), dotted, alias.name, fn_name)
                    )

        Visitor().visit(tree)

    return violations


def test_scalim_import_graph_is_acyclic() -> None:
    repo_root = _repo_root()
    src_root = repo_root / "src"
    scalim_root = src_root / "scalim"
    assert scalim_root.is_dir()

    py_files = _iter_py_files(scalim_root)

    module_for_path: Dict[Path, str] = {}
    path_for_module: Dict[str, Path] = {}
    for p in py_files:
        mod = _module_name_for_path(p, src_root=src_root)
        module_for_path[p] = mod
        path_for_module[mod] = p

    graph: Dict[str, Set[str]] = {m: set() for m in path_for_module}

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

            if getattr(node, "level", 0):
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

            # `from X import Y` depends at least on `X`
            if resolved in path_for_module:
                graph[current_module].add(resolved)

            # Heuristic: if `Y` is a module under `X`, record a direct edge to it as well.
            for alias in node.names:
                candidate = "{}.{}".format(resolved, alias.name)
                if candidate in path_for_module:
                    graph[current_module].add(candidate)

    sccs = _tarjan_scc(graph)
    cycles = [comp for comp in sccs if len(comp) > 1]
    assert not cycles, "import graph must be acyclic, found {} cycle(s):\n{}".format(
        len(cycles),
        "\n\n".join("\n".join(sorted(comp)) for comp in cycles),
    )


def test_main_package_has_no_function_local_imports() -> None:
    repo_root = _repo_root()
    scalim_root = repo_root / "src" / "scalim"
    assert scalim_root.is_dir()

    violations = _collect_function_local_imports(_iter_py_files(scalim_root), scalim_root=scalim_root)
    assert not violations, "function-local imports are forbidden in main package modules:\n{}".format("\n".join(violations))
