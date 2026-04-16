#!/usr/bin/env python3
"""Generate a snapshot catalog of public exports derived from module-level `__all__`.

This helper intentionally lives inside the change directory so we can iterate on the
catalog format while discussing `c1-simplify-public-run-api`, without turning it into
repo-wide SSOT prematurely.

Output:
  - `openspec/changes/c1-simplify-public-run-api/public-api-exports.md`

Notes:
  - Scan scope: `src/scalim/**/*.py`, excluding `src/scalim/vendor/**`.
  - The catalog is derived from AST parsing (no imports, no side effects).
  - The full catalog only includes modules with non-empty `__all__`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_PUBLIC_API_ENTRYPOINT_MARKER_RE = re.compile(
    r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|(?P<desc>[^|]*)\|(?P<scenario>.*)$",
    flags=re.IGNORECASE,
)

_UNKNOWN_GIT_HEAD = "(unknown)"


class PublicApiExportsError(RuntimeError):
    """本脚本的受控异常基类."""


class DuplicateTier1EntrypointMarkerError(PublicApiExportsError):
    def __init__(self, module: str) -> None:
        msg = "duplicate Tier 1 public API entrypoint markers for module: {}".format(str(module))
        super().__init__(msg)


class NoTier1EntrypointMarkersFoundError(PublicApiExportsError):
    def __init__(self) -> None:
        super().__init__("no Tier 1 public API entrypoints markers found under `src/scalim/**/__init__.py`")


def _repo_root() -> Path:
    # `<repo>/openspec/changes/c1-simplify-public-run-api/gen-public-api-exports.py`
    return Path(__file__).resolve().parents[3]


def _git_head(repo_root: Path) -> str:
    git_dir = repo_root / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return _UNKNOWN_GIT_HEAD

    if head.startswith("ref:"):
        ref = head.partition("ref:")[2].strip()
        if not ref:
            return _UNKNOWN_GIT_HEAD
        ref_path = git_dir / ref
        try:
            return ref_path.read_text(encoding="utf-8").strip() or _UNKNOWN_GIT_HEAD
        except OSError:
            return _UNKNOWN_GIT_HEAD

    return head or _UNKNOWN_GIT_HEAD


def _iter_py_files(root: Path, *, exclude_dirs: Sequence[Path]) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def _is_relative_to(path: Path, maybe_parent: Path) -> bool:
    try:
        path.relative_to(maybe_parent)
    except ValueError:
        return False
    else:
        return True


def _module_name_for_path(path: Path, *, src_root: Path) -> str:
    rel = path.relative_to(src_root)
    if rel.name == "__init__.py":
        rel = rel.parent
    else:
        rel = rel.with_suffix("")
    return ".".join(rel.parts)


def _extract_module_all(path: Path, *, repo_root: Path) -> Optional[Tuple[str, ...]]:
    """Return the last literal `__all__` assignment in the module, if any."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path.relative_to(repo_root)))

    last_value: Optional[ast.AST] = None
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                last_value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            last_value = node.value

    if last_value is None:
        return None

    if not isinstance(last_value, (ast.List, ast.Tuple)):
        return None

    values: List[str] = []
    for elt in list(last_value.elts):
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            values.append(str(elt.value))
            continue
        return None
    return tuple(values)


def _discover_curated_modules(*, repo_root: Path) -> List[str]:
    """Discover Tier 1 curated entrypoints from `__init__.py` markers.

    SSOT:
      `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
    """

    scan_root = repo_root / "src" / "scalim"
    exclude_dirs = (scan_root / "vendor",)

    found: Dict[str, int] = {}
    for path in sorted(scan_root.rglob("__init__.py")):
        if not path.is_file():
            continue
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _PUBLIC_API_ENTRYPOINT_MARKER_RE.match(line.strip())
            if not m:
                continue
            if int(m.group("tier")) != 1:
                continue
            module = str(m.group("module") or "").strip()
            if not module:
                continue
            order = int(m.group("order"))
            if module in found:
                raise DuplicateTier1EntrypointMarkerError(module)
            found[module] = order

    curated = [m for m, _ in sorted(found.items(), key=lambda item: (int(item[1]), str(item[0])))]
    if not curated:
        raise NoTier1EntrypointMarkersFoundError
    return curated


def _format_all_tuple(values: Tuple[str, ...]) -> List[str]:
    lines: List[str] = ["__all__ = ("]
    for name in values:
        lines.append("    {!r},".format(name))
    lines.append(")")
    return lines


def _render_catalog_header(*, repo_root: Path) -> List[str]:
    head = _git_head(repo_root)
    return [
        "# Public API exports catalog (snapshot)",
        "",
        "This file is generated for review/discussion in change `c1-simplify-public-run-api`.",
        "",
        "- Generated by: `python openspec/changes/c1-simplify-public-run-api/gen-public-api-exports.py`",
        "- Git HEAD: `{}`".format(head),
        "- Scan scope: `src/scalim/**/*.py` (excluding `src/scalim/vendor/**`)",
        "- SSOT: module-level `__all__` tuples in source files",
        "",
        "Regenerate:",
        "```bash",
        "python openspec/changes/c1-simplify-public-run-api/gen-public-api-exports.py",
        "```",
        "",
    ]


def _render_tier1_curated_overview(*, curated: Sequence[str], exports_by_module: Dict[str, Tuple[str, ...]]) -> List[str]:
    lines: List[str] = []
    lines.append("## Tier 1 curated entrypoints (from `# pragma: scalim-public-api tier1:...` markers)")
    lines.append("")
    lines.append("| module | exports |")
    lines.append("| --- | ---: |")
    for module in curated:
        exports = exports_by_module.get(str(module))
        count = len(exports) if exports is not None else "(missing __all__)"
        lines.append("| `{}` | {} |".format(str(module), count))
    lines.append("")
    return lines


def _render_module_exports_sections(*, modules: Sequence[str], exports_by_module: Dict[str, Tuple[str, ...]]) -> List[str]:
    lines: List[str] = []
    for module in modules:
        exports = exports_by_module.get(str(module))
        lines.append("### `{}`".format(str(module)))
        lines.append("")
        if exports is None:
            lines.append("- (missing `__all__` in scan scope)")
            lines.append("")
            continue
        lines.append("- Export count: `{}`".format(len(exports)))
        lines.append("")
        lines.append("```python")
        lines.extend(_format_all_tuple(exports))
        lines.append("```")
        lines.append("")
    return lines


def _render_full_catalog_overview(*, exports_by_module: Dict[str, Tuple[str, ...]]) -> List[str]:
    non_empty = {m: v for m, v in exports_by_module.items() if v}
    lines: List[str] = []
    lines.append("## Full catalog (modules with non-empty `__all__`)")
    lines.append("")
    lines.append("- Module count: `{}`".format(len(non_empty)))
    lines.append("")
    lines.append("| module | exports |")
    lines.append("| --- | ---: |")
    for module in sorted(non_empty.keys()):
        lines.append("| `{}` | {} |".format(str(module), len(non_empty[module])))
    lines.append("")
    return lines


def render_public_api_exports_markdown(*, repo_root: Path) -> str:
    src_root = repo_root / "src"
    scan_root = src_root / "scalim"
    exclude_dirs = (scan_root / "vendor",)

    exports_by_module: Dict[str, Tuple[str, ...]] = {}
    for path in _iter_py_files(scan_root, exclude_dirs=exclude_dirs):
        module = _module_name_for_path(path, src_root=src_root)
        exported = _extract_module_all(path, repo_root=repo_root)
        if exported is None:
            continue
        exports_by_module[module] = exported

    curated = _discover_curated_modules(repo_root=repo_root)
    non_empty_modules = sorted([m for m, v in exports_by_module.items() if v])

    out: List[str] = []
    out.extend(_render_catalog_header(repo_root=repo_root))
    out.extend(_render_tier1_curated_overview(curated=curated, exports_by_module=exports_by_module))
    out.extend(_render_module_exports_sections(modules=curated, exports_by_module=exports_by_module))
    out.extend(_render_full_catalog_overview(exports_by_module=exports_by_module))
    out.extend(_render_module_exports_sections(modules=non_empty_modules, exports_by_module=exports_by_module))

    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    repo_root = _repo_root()
    content = render_public_api_exports_markdown(repo_root=repo_root)
    output_path = repo_root / "openspec" / "changes" / "c1-simplify-public-run-api" / "public-api-exports.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    sys.stdout.write("wrote {}\n".format(output_path.relative_to(repo_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
