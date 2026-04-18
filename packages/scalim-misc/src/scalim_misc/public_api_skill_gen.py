from __future__ import annotations

import ast
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scalim_misc.public_api_suite_coverage import build_tier1_coverage_for_examples_suite, parse_public_api_pytest_chapter_ids

SKILL_NAME = "scalim-public-api"
SKILL_TITLE = "Scalim Public API (Tier1)"

FORBIDDEN_SKILL_ROOTS = (
    Path.home() / ".codex" / "skills",
    Path.home() / ".claude" / "skills",
    Path("/etc") / "codex" / "skills",
)

REFERENCES_ROOT_REL = Path("references")
GENERATED_ROOT_REL = REFERENCES_ROOT_REL / "generated"

TIER1_ENTRYPOINTS_REL = GENERATED_ROOT_REL / "tier1-entrypoints.gen.md"
TIER1_COVERAGE_REL = GENERATED_ROOT_REL / "tier1-suite-coverage.gen.md"

_ENTRYPOINT_MARKER_RE = re.compile(
    r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\.]+)\|(?P<desc>[^|]*)\|(?P<scenario>.*)$",
    flags=re.IGNORECASE,
)


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tier1Entrypoint:
    order: int
    module: str
    description: str
    common_scenario: str
    marker_relpath: str
    marker_lineno: int
    module_source_relpath: str
    exports: Tuple[str, ...]
    exports_kind: str
    exports_lineno: int


@dataclass(frozen=True)
class ModuleAllLiteral:
    values: Tuple[str, ...]
    kind: str
    lineno: int


def is_forbidden_output(path: Path) -> bool:
    for root in FORBIDDEN_SKILL_ROOTS:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        return True
    return False


def _path_to_posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        msg = f"读取失败: {path}: {exc}"
        raise GenerationError(msg) from exc


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _as_str_constant(node: ast.AST) -> Optional[str]:
    ast_str = getattr(ast, "Str", None)
    if ast_str is not None and isinstance(node, ast_str):  # pragma: no cover
        return str(getattr(node, "s", ""))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def _is_relative_to(path: Path, maybe_parent: Path) -> bool:
    try:
        path.relative_to(maybe_parent)
    except ValueError:
        return False
    return True


def _iter_tier1_marker_files(repo_root: Path) -> Iterable[Path]:
    scan_root = repo_root / "src" / "scalim"
    exclude_dirs = (scan_root / "vendor",)
    for path in sorted(scan_root.rglob("__init__.py"), key=str):
        if not path.is_file():
            continue
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def resolve_module_source_path(repo_root: Path, module: str) -> Optional[Path]:
    src_root = repo_root / "src"
    parts = [p for p in str(module).split(".") if p]
    if not parts:
        return None
    base = src_root.joinpath(*parts)
    pkg_init = base / "__init__.py"
    if pkg_init.is_file():
        return pkg_init
    mod_file = base.with_suffix(".py")
    if mod_file.is_file():
        return mod_file
    return None


def extract_literal_module_all(path: Path, *, repo_root: Path) -> Tuple[Optional[ModuleAllLiteral], Optional[str]]:
    tree, parse_err = _try_parse_python_ast(path, repo_root=repo_root)
    if tree is None:
        return None, parse_err

    last_value, last_lineno = _find_last_module_all_value(tree)
    if last_value is None:
        return None, "缺少字面量 `__all__` 赋值"

    values, kind, extract_err = _extract_module_all_values(last_value)
    if extract_err is not None:
        return None, extract_err

    lineno = int(last_lineno or 1)
    return ModuleAllLiteral(values=values, kind=kind, lineno=lineno), None


def _try_parse_python_ast(path: Path, *, repo_root: Path) -> Tuple[Optional[ast.AST], Optional[str]]:
    rel = _path_to_posix(path.relative_to(repo_root))
    text = _read_text(path)
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return None, f"AST 解析失败 (SyntaxError): {exc}"
    return tree, None


def _find_last_module_all_value(tree: ast.AST) -> Tuple[Optional[ast.AST], Optional[int]]:
    last_value: Optional[ast.AST] = None
    last_lineno: Optional[int] = None

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                last_value = node.value
                last_lineno = int(getattr(node, "lineno", 0) or 0) or None
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            last_value = node.value
            last_lineno = int(getattr(node, "lineno", 0) or 0) or None

    return last_value, last_lineno


def _extract_module_all_values(value: ast.AST) -> Tuple[Tuple[str, ...], str, Optional[str]]:
    if isinstance(value, ast.List):
        kind = "list"
        elts = list(value.elts)
    elif isinstance(value, ast.Tuple):
        kind = "tuple"
        elts = list(value.elts)
    else:
        return (
            (),
            "",
            "`__all__` 非字面量 (期望字符串常量组成的 list/tuple; 当前: {})".format(type(value).__name__),
        )

    values: List[str] = []
    for elt in elts:
        token = _as_str_constant(elt)
        if token is None:
            return (), "", "`__all__` 元素非字符串字面量 (期望 string constants)"
        values.append(token)

    return tuple(values), kind, None


def _parse_tier1_marker_match(
    match: re.Match[str],
    *,
    rel_marker: str,
    lineno: int,
) -> Tuple[Optional[Tuple[int, str, str, str]], Optional[str]]:
    module = str(match.group("module") or "").strip()
    desc = str(match.group("desc") or "").strip()
    scenario = str(match.group("scenario") or "").strip()
    order = int(match.group("order"))

    if not module:
        return None, "- {}:{}: tier1 标记缺少模块名".format(rel_marker, lineno)
    if not desc:
        return None, "- {}:{}: {}: tier1 标记缺少说明".format(rel_marker, lineno, module)
    if not scenario:
        return None, "- {}:{}: {}: tier1 标记缺少常见场景".format(rel_marker, lineno, module)

    return (order, module, desc, scenario), None


def _build_tier1_entrypoint(
    repo_root: Path,
    *,
    order: int,
    module: str,
    desc: str,
    scenario: str,
    rel_marker: str,
    lineno: int,
) -> Tuple[Optional[Tier1Entrypoint], Optional[str]]:
    module_path = resolve_module_source_path(repo_root, module)
    if module_path is None:
        problem = "- {}:{}: {}: 在 `src/` 下找不到模块 (期望存在 `src/{}.py` 或 `src/{}/__init__.py`)".format(
            rel_marker,
            lineno,
            module,
            module.replace(".", "/"),
            module.replace(".", "/"),
        )
        return None, problem

    all_literal, err = extract_literal_module_all(module_path, repo_root=repo_root)
    if all_literal is None:
        problem = "- {}:{}: {}: 入口模块必须声明字面量 `__all__` (模块文件: {}): {}".format(
            rel_marker,
            lineno,
            module,
            _path_to_posix(module_path.relative_to(repo_root)),
            str(err or "unknown error"),
        )
        return None, problem

    entry = Tier1Entrypoint(
        order=order,
        module=module,
        description=desc,
        common_scenario=scenario,
        marker_relpath=rel_marker,
        marker_lineno=lineno,
        module_source_relpath=_path_to_posix(module_path.relative_to(repo_root)),
        exports=tuple(all_literal.values),
        exports_kind=str(all_literal.kind),
        exports_lineno=int(all_literal.lineno),
    )
    return entry, None


def discover_tier1_entrypoints(repo_root: Path) -> Tuple[Tuple[Tier1Entrypoint, ...], Tuple[str, ...]]:
    problems: List[str] = []
    discovered: Dict[str, Tier1Entrypoint] = {}

    for path in _iter_tier1_marker_files(repo_root):
        text = _read_text(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _ENTRYPOINT_MARKER_RE.match(line.strip())
            if not m:
                continue
            if str(m.group("tier")) != "1":
                continue

            rel_marker = _path_to_posix(path.relative_to(repo_root))

            parsed, problem = _parse_tier1_marker_match(m, rel_marker=rel_marker, lineno=lineno)
            if problem is not None:
                problems.append(problem)
                continue
            if parsed is None:  # pragma: no cover
                problems.append("- {}:{}: tier1 标记解析失败".format(rel_marker, lineno))
                continue
            order, module, desc, scenario = parsed

            entry, problem = _build_tier1_entrypoint(
                repo_root,
                order=order,
                module=module,
                desc=desc,
                scenario=scenario,
                rel_marker=rel_marker,
                lineno=lineno,
            )
            if problem is not None:
                problems.append(problem)
                continue
            if entry is None:  # pragma: no cover
                problems.append("- {}:{}: {}: tier1 entrypoint 构建失败".format(rel_marker, lineno, module))
                continue

            if module in discovered:
                first = discovered[module]
                problems.append(
                    "- {}:{}: {}: 重复的 tier1 标记 (已在 {}:{} 声明)".format(
                        rel_marker,
                        lineno,
                        module,
                        first.marker_relpath,
                        first.marker_lineno,
                    )
                )
                continue
            discovered[module] = entry

    entrypoints = tuple(sorted(discovered.values(), key=lambda e: (int(e.order), str(e.module))))
    return entrypoints, tuple(problems)


def _render_tier1_entrypoints_markdown(entrypoints: Sequence[Tier1Entrypoint]) -> str:
    lines: List[str] = []
    lines.append("# {}".format(SKILL_TITLE))
    lines.append("")
    lines.append("此文档由 `scripts/gen-public-api-skill.py` 自动生成.")
    lines.append("")
    lines.append("## SSOT")
    lines.append("- Tier1 curated entrypoints markers: `src/scalim/**/__init__.py`")
    lines.append("- Entrypoint exports: 每个入口模块的字面量 `__all__` (AST 扫描; 不 import)")
    lines.append("")
    lines.append("## Tier1 Entrypoints ({})".format(len(entrypoints)))
    for entry in entrypoints:
        lines.append("")
        lines.append("### `{}` (order={})".format(entry.module, int(entry.order)))
        lines.append("- desc: {}".format(entry.description))
        lines.append("- scenario: {}".format(entry.common_scenario))
        lines.append("- marker: `{}:{}`".format(entry.marker_relpath, int(entry.marker_lineno)))
        lines.append("- source: `{}:{}`".format(entry.module_source_relpath, int(entry.exports_lineno)))
        lines.append("- exports (`__all__`, {}, count={}):".format(entry.exports_kind, len(entry.exports)))
        for name in entry.exports:
            lines.append("  - `{}`".format(name))
    lines.append("")
    return "\n".join(lines)


def _render_tier1_coverage_markdown(
    *,
    entrypoints: Sequence[Tier1Entrypoint],
    examples_coverage: Dict[str, Tuple[str, ...]],
    pytest_coverage: Dict[str, Tuple[str, ...]],
    pytest_chapter_ids: Sequence[str],
) -> str:
    lines: List[str] = []
    lines.append("# Tier1 Coverage Map (examples ↔ pytest)")
    lines.append("")
    lines.append("此文档由 `scripts/gen-public-api-skill.py` 自动生成.")
    lines.append("")
    lines.append("## Commands")
    lines.append("- Suite drift gate: `just check-public-api-suite-coverage`")
    lines.append("- Run examples: `just examples`")
    lines.append("- Run pytest public_api suite: `pytest -q tests/public_api/ --no-cov`")
    lines.append("- Full gate: `just qa`")
    lines.append("")
    lines.append("## Pytest Selected Chapters ({}):".format(len(pytest_chapter_ids)))
    for chapter_id in pytest_chapter_ids:
        lines.append("- `{}`".format(chapter_id))
    lines.append("")
    lines.append("## Tier1 Modules Coverage ({})".format(len(entrypoints)))
    lines.append("")
    for entry in entrypoints:
        module = entry.module
        examples = list(examples_coverage.get(module, ()))
        pytest = list(pytest_coverage.get(module, ()))

        lines.append("### `{}`".format(module))
        lines.append(
            "- examples chapters ({}): {}".format(len(examples), ", ".join("`{}`".format(c) for c in examples) if examples else "(missing)")
        )
        lines.append(
            "- pytest chapters ({}): {}".format(len(pytest), ", ".join("`{}`".format(c) for c in pytest) if pytest else "(missing)")
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _sync_generated_files(skill_dir: Path, generated_files: Dict[Path, str]) -> None:
    generated_root = skill_dir / GENERATED_ROOT_REL
    expected_paths = {skill_dir / rel_path for rel_path in generated_files}

    if generated_root.exists():
        for path in sorted(generated_root.rglob("*"), key=str, reverse=True):
            if path.is_file() and path not in expected_paths:
                path.unlink()
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    for rel_path, content in generated_files.items():
        _write_text(skill_dir / rel_path, content)


def _list_files(root: Path, base: Optional[Path] = None) -> List[str]:
    if base is None:
        base = root
    items: List[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            items.append(_path_to_posix(path.relative_to(base)))
    return sorted(items)


def list_managed_output_files(skill_dir: Path) -> List[str]:
    generated_root = skill_dir / GENERATED_ROOT_REL
    if not generated_root.exists():
        return []
    return _list_files(generated_root, base=skill_dir)


def build_skill(repo_root: Path, output_root: Path) -> List[str]:
    skill_dir = output_root / SKILL_NAME
    if is_forbidden_output(skill_dir):
        msg = "拒绝写入到用户技能目录下."
        raise GenerationError(msg)

    entrypoints, problems = discover_tier1_entrypoints(repo_root)
    if problems:
        msg = "Tier1 curated entrypoints 存在问题:\n{}".format("\n".join(problems))
        raise GenerationError(msg)

    tier1_modules = {e.module for e in entrypoints}
    examples_cov = build_tier1_coverage_for_examples_suite(repo_root, tier1_modules)
    pytest_chapter_ids = parse_public_api_pytest_chapter_ids(repo_root)
    pytest_cov = build_tier1_coverage_for_examples_suite(repo_root, tier1_modules, chapter_ids=pytest_chapter_ids)

    missing_in_examples = sorted(tier1_modules.difference(examples_cov.covered_modules))
    missing_in_pytest = sorted(tier1_modules.difference(pytest_cov.covered_modules))
    if missing_in_examples or missing_in_pytest:
        msg_lines = ["Tier1 覆盖缺失;请先补齐 examples/pytest public_api suite,再生成 references."]
        if missing_in_examples:
            msg_lines.append("- examples missing: {}".format(", ".join(missing_in_examples)))
        if missing_in_pytest:
            msg_lines.append("- pytest missing: {}".format(", ".join(missing_in_pytest)))
        msg_lines.append("修复入口:")
        msg_lines.append("- add chapters: notebooks/marimo/example_public_api_suite/chapters/")
        msg_lines.append("- update pytest selection: tests/public_api/test_example_public_api_suite.py")
        raise GenerationError("\n".join(msg_lines))

    generated_files = {
        TIER1_ENTRYPOINTS_REL: _render_tier1_entrypoints_markdown(entrypoints).rstrip() + "\n",
        TIER1_COVERAGE_REL: _render_tier1_coverage_markdown(
            entrypoints=entrypoints,
            examples_coverage=examples_cov.module_to_chapter_ids,
            pytest_coverage=pytest_cov.module_to_chapter_ids,
            pytest_chapter_ids=pytest_chapter_ids,
        ),
    }
    _sync_generated_files(skill_dir, generated_files)
    return list_managed_output_files(skill_dir)


def validate_skill(repo_root: Path, output_root: Path) -> bool:
    skill_dir = output_root / SKILL_NAME
    generated_root = skill_dir / GENERATED_ROOT_REL

    if not generated_root.exists():
        sys.stderr.write("未找到 `references/generated/` 目录: {}\n".format(generated_root))
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        build_skill(repo_root, tmp_root)
        tmp_skill_dir = tmp_root / SKILL_NAME

        expected_files = list_managed_output_files(tmp_skill_dir)
        actual_files = list_managed_output_files(skill_dir)
        if expected_files != actual_files:
            sys.stderr.write("受控参考文件集合不一致.\n")
            sys.stderr.write("期望: {}\n".format(expected_files))
            sys.stderr.write("实际: {}\n".format(actual_files))
            return False

        for rel_path in expected_files:
            expected_path = tmp_skill_dir / rel_path
            actual_path = skill_dir / rel_path
            if expected_path.read_bytes() != actual_path.read_bytes():
                sys.stderr.write("检测到受控产物内容漂移: {}\n".format(rel_path))
                return False

    return True
