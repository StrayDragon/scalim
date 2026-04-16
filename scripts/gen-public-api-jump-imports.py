#!/usr/bin/env python3
"""生成一个 `.tmp/` 内的“public API 跳转辅助 imports”文件.

目的:
- 方便在编辑器/LSP 中快速跳转到 public API 符号定义(无需在项目里手写大量 import)。
- 生成物放在 `.tmp/`，不提交，也不影响 `basedpyright` 门禁。

SSOT:
- Tier 1 curated entrypoints 通过 `src/scalim/**/__init__.py` 中的注释标注发现:
  `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
- 每个模块的导出符号集合来自该模块的 `__all__` 字面量(tuple/list)。
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class PublicApiEntrypoint:
    order: int
    module: str
    description: str
    common_scenario: str


_MARKER_RE = re.compile(
    r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|(?P<desc>[^|]*)\|(?P<scenario>.*)$",
    flags=re.IGNORECASE,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_relative_to(path: Path, maybe_parent: Path) -> bool:
    try:
        path.relative_to(maybe_parent)
    except ValueError:
        return False
    return True


def _discover_entrypoints(repo_root: Path, *, tier: int) -> Tuple[PublicApiEntrypoint, ...]:
    scan_root = repo_root / "src" / "scalim"
    exclude_dirs = (scan_root / "vendor",)

    entrypoints: List[PublicApiEntrypoint] = []
    errors: List[str] = []

    for path in sorted(scan_root.rglob("__init__.py"), key=lambda p: str(p)):
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _MARKER_RE.match(line.strip())
            if not m:
                continue
            got_tier = int(m.group("tier"))
            if got_tier != int(tier):
                continue
            order = int(m.group("order"))
            module = str(m.group("module") or "").strip()
            desc = str(m.group("desc") or "").strip()
            scenario = str(m.group("scenario") or "").strip()
            if not module:
                errors.append("{}:{}: missing module".format(rel, lineno))
                continue
            if not desc:
                errors.append("{}:{}: missing description for {}".format(rel, lineno, module))
                continue
            if not scenario:
                errors.append("{}:{}: missing scenario for {}".format(rel, lineno, module))
                continue
            entrypoints.append(PublicApiEntrypoint(order=order, module=module, description=desc, common_scenario=scenario))

    if errors:
        raise RuntimeError(
            "public API entrypoints markers invalid (showing up to 20):\n{}".format("\n".join("- {}".format(e) for e in errors[:20]))
        )

    by_module: Dict[str, PublicApiEntrypoint] = {}
    duplicates: List[str] = []
    for entry in entrypoints:
        if entry.module in by_module:
            duplicates.append(entry.module)
            continue
        by_module[entry.module] = entry
    if duplicates:
        raise RuntimeError("duplicate public API entrypoints markers: {}".format(", ".join(sorted(set(duplicates)))))

    discovered = sorted(by_module.values(), key=lambda e: (int(e.order), str(e.module)))
    if not discovered:
        raise RuntimeError("no public API entrypoints markers found for tier={}".format(tier))
    return tuple(discovered)


def _iter_py_files(root: Path, *, exclude_dirs: Sequence[Path]) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py"), key=lambda p: str(p)):
        if not path.is_file():
            continue
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def _module_name_for_path(path: Path, *, src_root: Path) -> str:
    rel = path.relative_to(src_root)
    if rel.name == "__init__.py":
        rel = rel.parent
    else:
        rel = rel.with_suffix("")
    return ".".join(rel.parts)


def _extract_module_all(path: Path, *, repo_root: Path) -> Tuple[str, ...] | None:
    """Return the last literal `__all__` assignment in the module, if any."""
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(repo_root)).replace("\\", "/")
    tree = ast.parse(text, filename=rel)

    last_value: ast.AST | None = None
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


def _scan_public_exports(repo_root: Path) -> Dict[str, Tuple[str, ...]]:
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
    return all_by_module


def _as_ident(value: str) -> str:
    # Module name -> valid python identifier
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))


def _render_jump_file(
    entrypoints: Sequence[PublicApiEntrypoint],
    *,
    exports_by_module: Dict[str, Tuple[str, ...]],
    generated_by: str,
) -> str:
    lines: List[str] = [
        "# This file is generated. Do not edit or commit.",
        "#",
        "# Generated by: {}".format(generated_by),
        "# Purpose: editor/LSP jump-to-definition helpers for Tier 1 public API.",
        "#",
        "from __future__ import annotations",
        "",
        "from typing import TYPE_CHECKING",
        "",
        "if TYPE_CHECKING:",
    ]

    for entry in entrypoints:
        exports = exports_by_module.get(entry.module)
        if exports is None:
            raise RuntimeError("missing `__all__` for curated module: {}".format(entry.module))

        func_name = "_jump_{}".format(_as_ident(entry.module))
        lines.append("    def {}() -> None:".format(func_name))
        lines.append("        \"\"\"{} | {}\"\"\"".format(entry.description, entry.common_scenario))

        if not exports:
            lines.append("        return")
            lines.append("")
            continue

        lines.append("        from {} import (".format(entry.module))
        for name in exports:
            if not str(name).isidentifier():
                # 极少见: 若 `__all__` 里出现非法标识符,这里跳过以保证生成物可解析.
                continue
            lines.append("            {},".format(name))
        lines.append("        )")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    repo_root = _repo_root()
    entrypoints = _discover_entrypoints(repo_root, tier=1)
    exports_by_module = _scan_public_exports(repo_root)

    out_dir = repo_root / ".tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "public_api_jump_imports.py"
    out_path.write_text(
        _render_jump_file(
            entrypoints,
            exports_by_module=exports_by_module,
            generated_by="python scripts/gen-public-api-jump-imports.py",
        ),
        encoding="utf-8",
    )
    print("wrote", str(out_path.relative_to(repo_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

