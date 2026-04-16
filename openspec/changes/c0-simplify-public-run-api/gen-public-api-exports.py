#!/usr/bin/env python3
"""Generate a snapshot catalog of public exports derived from module-level `__all__`.

This helper intentionally lives inside the change directory so we can iterate on the
catalog format while discussing `c0-simplify-public-run-api`, without turning it into
repo-wide SSOT prematurely.

Output:
  - `openspec/changes/c0-simplify-public-run-api/public-api-exports.md`

Notes:
  - Scan scope: `src/scalim/**/*.py`, excluding `src/scalim/vendor/**`.
  - The catalog is derived from AST parsing (no imports, no side effects).
  - The full catalog only includes modules with non-empty `__all__`.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


_PUBLIC_API_ENTRYPOINT_MARKER_RE = re.compile(
    r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|(?P<desc>[^|]*)\|(?P<scenario>.*)$",
    flags=re.IGNORECASE,
)


def _repo_root() -> Path:
    # `<repo>/openspec/changes/c0-simplify-public-run-api/gen-public-api-exports.py`
    return Path(__file__).resolve().parents[3]


def _git_head(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_root))
        return out.decode("utf-8").strip()
    except Exception:
        return "(unknown)"


def _iter_py_files(root: Path, *, exclude_dirs: Sequence[Path]) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def _is_relative_to(path: Path, maybe_parent: Path) -> bool:
    try:
        _ = path.relative_to(maybe_parent)
        return True
    except ValueError:
        return False


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
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
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
                raise RuntimeError("duplicate Tier 1 public API entrypoint markers for module: {}".format(module))
            found[module] = order

    curated = [m for m, _ in sorted(found.items(), key=lambda item: (int(item[1]), str(item[0])))]
    if not curated:
        raise RuntimeError("no Tier 1 public API entrypoints markers found under `src/scalim/**/__init__.py`")
    return curated


def _format_all_tuple(values: Tuple[str, ...]) -> List[str]:
    lines: List[str] = ["__all__ = ("]
    for name in values:
        lines.append("    {!r},".format(name))
    lines.append(")")
    return lines


def render_public_api_exports_markdown(*, repo_root: Path) -> str:
    src_root = repo_root / "src"
    scan_root = src_root / "scalim"
    exclude_dirs = (scan_root / "vendor",)

    all_by_module: Dict[str, Tuple[str, ...]] = {}
    for path in _iter_py_files(scan_root, exclude_dirs=exclude_dirs):
        mod = _module_name_for_path(path, src_root=src_root)
        exported = _extract_module_all(path, repo_root=repo_root)
        if exported is None:
            continue
        all_by_module[mod] = exported

    curated = _discover_curated_modules(repo_root=repo_root)
    non_empty = {m: v for m, v in all_by_module.items() if v}

    out: List[str] = []
    out.append("# Public API exports catalog (snapshot)")
    out.append("")
    out.append("This file is generated for review/discussion in change `c0-simplify-public-run-api`.")
    out.append("")
    out.append("- Generated by: `python openspec/changes/c0-simplify-public-run-api/gen-public-api-exports.py`")
    out.append("- Git HEAD: `{}`".format(_git_head(repo_root)))
    out.append("- Scan scope: `src/scalim/**/*.py` (excluding `src/scalim/vendor/**`)")
    out.append("- SSOT: module-level `__all__` tuples in source files")
    out.append("")
    out.append("Regenerate:")
    out.append("```bash")
    out.append("python openspec/changes/c0-simplify-public-run-api/gen-public-api-exports.py")
    out.append("```")
    out.append("")

    # --- Curated Tier 1
    out.append("## Tier 1 curated entrypoints (from `# pragma: scalim-public-api tier1:...` markers)")
    out.append("")
    out.append("| module | exports |")
    out.append("| --- | ---: |")
    for mod in curated:
        exports = all_by_module.get(mod)
        out.append("| `{}` | {} |".format(mod, len(exports) if exports is not None else "(missing __all__)"))
    out.append("")

    for mod in curated:
        exports = all_by_module.get(mod)
        out.append("### `{}`".format(mod))
        out.append("")
        if exports is None:
            out.append("- (missing `__all__` in scan scope)")
            out.append("")
            continue
        out.append("- Export count: `{}`".format(len(exports)))
        out.append("")
        out.append("```python")
        out.extend(_format_all_tuple(exports))
        out.append("```")
        out.append("")

    # --- Full catalog
    out.append("## Full catalog (modules with non-empty `__all__`)")
    out.append("")
    out.append("- Module count: `{}`".format(len(non_empty)))
    out.append("")
    out.append("| module | exports |")
    out.append("| --- | ---: |")
    for mod in sorted(non_empty.keys()):
        out.append("| `{}` | {} |".format(mod, len(non_empty[mod])))
    out.append("")

    for mod in sorted(non_empty.keys()):
        exports = non_empty[mod]
        out.append("### `{}`".format(mod))
        out.append("")
        out.append("- Export count: `{}`".format(len(exports)))
        out.append("")
        out.append("```python")
        out.extend(_format_all_tuple(exports))
        out.append("```")
        out.append("")

    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    repo_root = _repo_root()
    content = render_public_api_exports_markdown(repo_root=repo_root)
    output_path = repo_root / "openspec" / "changes" / "c0-simplify-public-run-api" / "public-api-exports.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print("wrote", str(output_path.relative_to(repo_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
