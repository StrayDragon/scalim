import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from tests.support.pathing import tests_root as _tests_root

_ALLOWED_TESTS_REF_PREFIX = "tests.fixtures"
_TESTS_REF_START_RE = re.compile(r"tests\\.[A-Za-z_]")


@dataclass(frozen=True)
class _Violation:
    path: Path
    lineno: int
    ref: str


def _is_allowed_tests_ref(ref: str) -> bool:
    return ref == _ALLOWED_TESTS_REF_PREFIX or ref.startswith(_ALLOWED_TESTS_REF_PREFIX + ".")


def _extract_tests_refs_from_line(line: str) -> Sequence[str]:
    refs: List[str] = []
    idx = 0
    while True:
        match = _TESTS_REF_START_RE.search(line, idx)
        if match is None:
            break
        start = match.start()
        end = start
        while end < len(line) and (line[end].isalnum() or line[end] in "._"):
            end += 1
        refs.append(line[start:end])
        idx = end
    return refs


def _scan_text(path: Path, base_lineno: int, text: str) -> Sequence[_Violation]:
    violations: List[_Violation] = []
    for offset, line in enumerate(text.splitlines()):
        lineno = base_lineno + offset
        for ref in _extract_tests_refs_from_line(line):
            if not _is_allowed_tests_ref(ref):
                violations.append(_Violation(path=path, lineno=lineno, ref=ref))
    return violations


def _scan_python_string_literals(path: Path) -> Sequence[_Violation]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        msg = "governance scan failed to parse python file: {} ({})".format(path, exc)
        raise AssertionError(msg) from exc

    violations: List[_Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            violations.extend(_scan_text(path, getattr(node, "lineno", 1), node.value))
    return violations


def _scan_yaml_file(path: Path) -> Sequence[_Violation]:
    violations: List[_Violation] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for ref in _extract_tests_refs_from_line(line):
            if not _is_allowed_tests_ref(ref):
                violations.append(_Violation(path=path, lineno=lineno, ref=ref))
    return violations


def test_domain_suite_directories_exist() -> None:
    root = _tests_root()
    required = (
        "bench",
        "execution",
        "fixtures",
        "governance",
        "integration",
        "ob",
        "planning",
        "public_api",
        "sinks",
        "support",
        "workflow",
        "yaml_dsl",
    )
    missing = [d for d in required if not (root / d).is_dir()]
    assert not missing, "missing required domain suite directories: {}".format(", ".join(missing))

    unexpected_root_tests = sorted(p.name for p in root.glob("test_*.py"))
    assert not unexpected_root_tests, "move tests/{} into a domain suite directory".format(", ".join(unexpected_root_tests))


def test_yaml_string_reference_boundary_is_enforced() -> None:
    root = _tests_root()

    violations: List[_Violation] = []

    for py_path in sorted(root.rglob("*.py")):
        violations.extend(_scan_python_string_literals(py_path))

    for yaml_path in sorted(list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))):
        violations.extend(_scan_yaml_file(yaml_path))

    assert not violations, (
        "Found forbidden `tests.*` string references outside `{}`. "
        "Move the referenced callable/module into `tests/fixtures/` and reference it as `{}`.\n{}".format(
            _ALLOWED_TESTS_REF_PREFIX,
            _ALLOWED_TESTS_REF_PREFIX + ".<module>",
            "\n".join(
                "{}:{}: {}".format(v.path.as_posix(), v.lineno, v.ref)
                for v in sorted(violations, key=lambda v: (v.path.as_posix(), v.lineno, v.ref))
            ),
        )
    )


def test_no_additional_test_files_exist() -> None:
    root = _tests_root()
    additional = sorted(p.relative_to(root).as_posix() for p in root.rglob("test_*_additional.py"))
    assert not additional, "merge these files back into the domain suite SSOT (do not use *_additional): {}".format(", ".join(additional))
