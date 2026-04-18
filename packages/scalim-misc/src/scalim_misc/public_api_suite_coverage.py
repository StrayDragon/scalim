from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence, Set, Tuple

if TYPE_CHECKING:
    from pathlib import Path


class CoverageError(RuntimeError):
    pass


_CHAPTER_FILE_RE = re.compile(r"^(ch\d+_[a-z][a-z0-9_]+)\.py$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Tier1Coverage:
    covered_modules: Tuple[str, ...]
    module_to_chapter_ids: Dict[str, Tuple[str, ...]]


def _as_str_constant(node: ast.AST) -> Optional[str]:
    ast_str = getattr(ast, "Str", None)
    if ast_str is not None and isinstance(node, ast_str):  # pragma: no cover - for old runtimes
        return str(getattr(node, "s", ""))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        msg = f"读取失败: {path}: {exc}"
        raise CoverageError(msg) from exc


def _parse_python_ast(*, text: str, path: Path) -> ast.AST:
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        msg = f"章节 AST 解析失败: {path}: {exc}"
        raise CoverageError(msg) from exc


def iter_example_public_api_suite_chapters(repo_root: Path) -> Iterable[Path]:
    chapters_root = repo_root / "notebooks" / "marimo" / "example_public_api_suite" / "chapters"
    if not chapters_root.exists():
        msg = f"未找到 examples suite chapters 目录: {chapters_root}"
        raise CoverageError(msg)

    for path in sorted(chapters_root.glob("*.py"), key=str):
        if path.name == "registry.py":
            continue
        m = _CHAPTER_FILE_RE.match(path.name)
        if not m:
            continue
        yield path


def _raise_literal_str_seq_error(*, label: str, path: Path) -> None:
    msg = f"{label} 必须是字符串字面量组成的 list/tuple: {path}"
    raise CoverageError(msg)


def _extract_literal_str_seq(node: ast.AST, *, label: str, path: Path) -> Tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        _raise_literal_str_seq_error(label=label, path=path)
    items = list(node.elts)

    values: List[str] = []
    for item in items:
        value = _as_str_constant(item)
        if value is None:
            _raise_literal_str_seq_error(label=label, path=path)
        token = str(value).strip()
        if token:
            values.append(token)
    return tuple(values)


def extract_declared_tier1_modules(path: Path) -> Tuple[str, ...]:
    """读取章节中显式声明的覆盖集合.

    约定:
      - `COVERS_TIER1_MODULES = (...)`
      - 仅允许字符串字面量组成的 list/tuple
    """

    text = _read_text(path)
    tree = _parse_python_ast(text=text, path=path)

    last_value: Optional[ast.AST] = None
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "COVERS_TIER1_MODULES" for t in node.targets):
                last_value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "COVERS_TIER1_MODULES":
            last_value = node.value

    if last_value is None:
        return ()

    return _extract_literal_str_seq(last_value, label="COVERS_TIER1_MODULES", path=path)


class _ImportCandidateVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.candidates: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = str(getattr(alias, "name", "") or "").strip()
            if name.startswith("scalim"):
                self.candidates.add(name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            return

        module = str(getattr(node, "module", "") or "").strip()
        if not module.startswith("scalim"):
            return

        if module:
            self.candidates.add(module)

        for alias in node.names:
            child = str(getattr(alias, "name", "") or "").strip()
            if not child or child == "*":
                continue
            if not _IDENTIFIER_RE.match(child):
                continue
            self.candidates.add(f"{module}.{child}")


def extract_import_module_candidates(path: Path) -> Tuple[str, ...]:
    text = _read_text(path)
    tree = _parse_python_ast(text=text, path=path)
    visitor = _ImportCandidateVisitor()
    visitor.visit(tree)
    return tuple(sorted(visitor.candidates))


def _chapter_id_for_path(path: Path) -> str:
    return str(path.stem)


def build_tier1_coverage_for_examples_suite(
    repo_root: Path,
    tier1_modules: Set[str],
    *,
    chapter_ids: Optional[Sequence[str]] = None,
) -> Tier1Coverage:
    selected: Optional[Set[str]] = None
    if chapter_ids is not None:
        selected = {str(item) for item in chapter_ids}

    module_to_chapters: Dict[str, Set[str]] = {}

    for chapter_path in iter_example_public_api_suite_chapters(repo_root):
        chapter_id = _chapter_id_for_path(chapter_path)
        if selected is not None and chapter_id not in selected:
            continue

        declared = set(extract_declared_tier1_modules(chapter_path))
        imported_candidates = set(extract_import_module_candidates(chapter_path))
        candidates = declared | imported_candidates
        covered_set: Set[str] = set()
        for candidate in candidates:
            parts = [p for p in str(candidate).split(".") if p]
            for end in range(1, len(parts) + 1):
                prefix = ".".join(parts[:end])
                if prefix in tier1_modules:
                    covered_set.add(prefix)
        covered = sorted(covered_set)
        for module in covered:
            module_to_chapters.setdefault(module, set()).add(chapter_id)

    covered_modules = tuple(sorted(module_to_chapters))
    module_to_chapter_ids = {module: tuple(sorted(chapters)) for module, chapters in module_to_chapters.items()}
    return Tier1Coverage(covered_modules=covered_modules, module_to_chapter_ids=module_to_chapter_ids)


def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return str(node.id)
    if isinstance(node, ast.Attribute):
        return str(node.attr)
    return None


def _find_keyword_value(call: ast.Call, *, keyword: str) -> Optional[ast.AST]:
    for kw in call.keywords:
        if str(getattr(kw, "arg", "") or "") == keyword and kw.value is not None:
            return kw.value
    return None


def parse_public_api_pytest_chapter_ids(repo_root: Path) -> Tuple[str, ...]:
    test_path = repo_root / "tests" / "public_api" / "test_example_public_api_suite.py"
    if not test_path.exists():
        msg = f"未找到 pytest public_api suite 入口: {test_path}"
        raise CoverageError(msg)

    text = _read_text(test_path)
    try:
        tree = ast.parse(text, filename=str(test_path))
    except SyntaxError as exc:  # pragma: no cover
        msg = f"pytest public_api suite AST 解析失败: {test_path}: {exc}"
        raise CoverageError(msg) from exc

    chapter_ids: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = _call_name(node.func)
        if func_name != "run_selected_chapters":
            continue

        chapter_ids_node = _find_keyword_value(node, keyword="chapter_ids")
        if chapter_ids_node is None:
            continue
        items = _extract_literal_str_seq(chapter_ids_node, label="chapter_ids", path=test_path)
        chapter_ids.extend(items)

    unique = tuple(sorted({str(item) for item in chapter_ids if str(item).strip()}))
    if not unique:
        msg = f"未能从 pytest public_api suite 提取 chapter_ids: {test_path}"
        raise CoverageError(msg)
    return unique
