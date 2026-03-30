import ast
from pathlib import Path
from typing import List, Optional

from tests.support.pathing import repo_root as _repo_root


def _iter_py_files(root: Path) -> List[Path]:
    return sorted([p for p in root.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts])


def _is_importing_dsl(module: Optional[str], *, is_relative: bool) -> bool:
    if not module:
        return False
    if not is_relative:
        return module == "scalim.dsl" or module.startswith("scalim.dsl.")
    # Relative imports inside `scalim.workflow.*` must not reach `scalim.dsl.*`.
    return module.split(".")[0] == "dsl"


def _extract_import_dsl_violations(src: str, *, file_path: Path) -> List[str]:
    tree = ast.parse(src, filename=str(file_path))

    violations: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_importing_dsl(alias.name, is_relative=False):
                    violations.append("{}: import {!r}".format(file_path, alias.name))

        if isinstance(node, ast.ImportFrom):
            is_relative = bool(getattr(node, "level", 0))
            module = getattr(node, "module", None)
            if _is_importing_dsl(module, is_relative=is_relative):
                violations.append("{}: from {}{!r} import ...".format(file_path, "." * int(getattr(node, "level", 0)), module))

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
                violations.append("{}: dynamic import {!r} via {}".format(file_path, mod, func_name))

    return violations


def test_workflow_framework_must_not_import_dsl_modules() -> None:
    repo_root = _repo_root()
    workflow_root = repo_root / "src" / "scalim" / "workflow"
    assert workflow_root.is_dir()

    violations: List[str] = []
    for p in _iter_py_files(workflow_root):
        src = p.read_text(encoding="utf-8")
        violations.extend(_extract_import_dsl_violations(src, file_path=p))

    assert not violations, "workflow layer must not import dsl modules:\n{}".format("\n".join(violations))


def test_by_yaml_runtime_must_not_contain_workflow_runtime_modules() -> None:
    repo_root = _repo_root()
    runtime_root = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "runtime"
    assert runtime_root.is_dir()

    workflow_runtime_files = sorted([p.relative_to(runtime_root).as_posix() for p in runtime_root.rglob("workflow_*.py")])
    assert not workflow_runtime_files, "by_yaml/runtime must not contain workflow runtime modules:\n{}".format(
        "\n".join(workflow_runtime_files)
    )
