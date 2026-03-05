import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional


def _iter_python_files(root_dir: Path) -> Iterator[Path]:
    for path in root_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _find_execution_imports(source: str, *, path: Path) -> List[str]:
    tree = ast.parse(source, filename=str(path))
    findings: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scalim.execution" or alias.name.startswith("scalim.execution."):
                    findings.append("{}:{}: import {}".format(path, getattr(node, "lineno", "?"), alias.name))
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        module: Optional[str] = node.module
        level = node.level

        # Absolute import: `from scalim.execution... import ...`
        if level == 0:
            if module and (module == "scalim.execution" or module.startswith("scalim.execution.")):
                findings.append("{}:{}: from {}".format(path, getattr(node, "lineno", "?"), module))
            continue

        # Relative import: `from ..execution... import ...` (level>=2 reaches `scalim.*` from inside `scalim.planning.*`)
        if module and (module == "execution" or module.startswith("execution.")) and level >= 2:
            findings.append("{}:{}: from {}{}".format(path, getattr(node, "lineno", "?"), "." * level, module))
            continue

        # Relative import without module: `from .. import execution`
        if module is None and level >= 2:
            for alias in node.names:
                if alias.name == "execution":
                    findings.append("{}:{}: from {} import execution".format(path, getattr(node, "lineno", "?"), "." * level))
                    break

    return findings


def test_planning_does_not_import_execution() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    planning_dir = repo_root / "src" / "scalim" / "planning"

    violations: List[str] = []
    for path in _iter_python_files(planning_dir):
        source = path.read_text(encoding="utf-8")
        violations.extend(_find_execution_imports(source, path=path))

    assert not violations, "planning must not import execution:\n{}".format("\n".join(sorted(violations)))


def test_planning_import_does_not_pull_execution_side_effects() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)

    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    code = (
        "import sys\n"
        "import scalim.planning.builder\n"
        "import scalim.planning.plan\n"
        "mods = sorted(m for m in sys.modules if m.startswith('scalim.execution'))\n"
        "print('\\n'.join(mods))\n"
    )
    output = subprocess.check_output([sys.executable, "-c", code], cwd=str(repo_root), env=env, universal_newlines=True)

    assert output.strip() == "", "planning import should not load scalim.execution modules:\n{}".format(output)
