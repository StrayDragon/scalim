#!/usr/bin/env python3
"""生成可审阅的第 1 层（`tier1`）公共接口导出审计视图.

输出:
  - `.tmp/public_api_exports_catalog.md`

`SSOT`:
  - `src/scalim/**/__init__.py` 中的 `tier1` 标记:
      `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
  - 各模块的字面量 `__all__`（仅 `AST` 扫描；不 `import`）。

约束:
  - 生成物写入 `.tmp/`，用于评审/排错/对齐；不要提交。
  - 输出确定性：不包含时间戳 / `git` 元信息。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from public_api_tooling import (
    PublicApiEntrypointMarker,
    PublicApiProblem,
    extract_literal_module_all,
    discover_public_api_entrypoints,
    repo_root_for_script,
    resolve_module_source_path,
)


def _as_relpath(path: Path, *, repo_root: Path) -> str:
    return str(path.relative_to(repo_root)).replace("\\", "/")


def _write_text(path: Path, content: str) -> None:
    if content and not content.endswith("\n"):
        content += "\n"
    if path.exists() and path.is_symlink():
        raise RuntimeError("拒绝覆盖软链文件: {}".format(str(path)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _format_all_tuple(values: Tuple[str, ...]) -> Iterable[str]:
    yield "__all__ = ("
    for name in values:
        yield "    {!r},".format(str(name))
    yield ")"


def _render_header() -> List[str]:
    return [
        "<!--",
        "本文件由 `just gen-public-api-exports-catalog` 自动生成 (scripts/gen-public-api-exports-catalog.py).",
        "产物写入 `.tmp/`，用于 review/审计；不要编辑或提交.",
        "-->",
        "",
        "# Public API exports catalog (Tier 1 curated entrypoints)",
        "",
        "Regenerate:",
        "```bash",
        "just gen-public-api-exports-catalog",
        "```",
        "",
    ]


def _render_overview_table(entrypoints: Sequence[PublicApiEntrypointMarker], exports_by_module: dict[str, Tuple[str, ...]]) -> List[str]:
    lines: List[str] = []
    lines.append("## Overview")
    lines.append("")
    lines.append("| module | exports | description | common scenario |")
    lines.append("| --- | ---: | --- | --- |")
    for entry in entrypoints:
        exports = exports_by_module[str(entry.module)]
        lines.append("| `{}` | {} | {} | {} |".format(entry.module, len(exports), entry.description, entry.common_scenario))
    lines.append("")
    return lines


def _render_entrypoints_sections(
    entrypoints: Sequence[PublicApiEntrypointMarker], exports_by_module: dict[str, Tuple[str, ...]]
) -> List[str]:
    lines: List[str] = []
    lines.append("## Entrypoints")
    lines.append("")
    for entry in entrypoints:
        exports = exports_by_module[str(entry.module)]
        lines.append("### `{}`".format(entry.module))
        lines.append("")
        lines.append("- Marker: `{}`:{}".format(_as_relpath(entry.marker_path, repo_root=_REPO_ROOT), entry.marker_lineno))
        lines.append("- Description: {}".format(entry.description))
        lines.append("- Common scenario: {}".format(entry.common_scenario))
        lines.append("- Export count: `{}`".format(len(exports)))
        lines.append("")
        lines.append("```python")
        lines.extend(list(_format_all_tuple(exports)))
        lines.append("```")
        lines.append("")
    return lines


def _format_problems(problems: Sequence[PublicApiProblem], *, repo_root: Path) -> str:
    lines: List[str] = []
    for p in problems:
        rel = _as_relpath(p.path, repo_root=repo_root) if p.path.exists() else str(p.path)
        module = str(p.module or "(unknown)")
        lines.append("- {}:{}: {}: {}".format(rel, int(p.lineno), module, p.reason))
    return "\n".join(lines)


def _collect_exports_or_problems(
    entrypoints: Sequence[PublicApiEntrypointMarker], *, repo_root: Path
) -> Tuple[dict[str, Tuple[str, ...]], Tuple[PublicApiProblem, ...]]:
    problems: List[PublicApiProblem] = []
    exports_by_module: dict[str, Tuple[str, ...]] = {}

    for entry in entrypoints:
        module_path = resolve_module_source_path(repo_root, entry.module)
        if module_path is None:
            problems.append(
                PublicApiProblem(
                    path=entry.marker_path,
                    lineno=entry.marker_lineno,
                    module=entry.module,
                    reason="在 `src/` 下找不到入口模块（期望存在 `src/{}.py` 或 `src/{}/__init__.py`）".format(
                        entry.module.replace(".", "/"),
                        entry.module.replace(".", "/"),
                    ),
                )
            )
            continue

        all_literal, err = extract_literal_module_all(module_path, repo_root=repo_root)
        if all_literal is None:
            problems.append(
                PublicApiProblem(
                    path=entry.marker_path,
                    lineno=entry.marker_lineno,
                    module=entry.module,
                    reason="入口模块必须声明字面量 `__all__`（模块文件: {}）：{}".format(
                        _as_relpath(module_path, repo_root=repo_root),
                        str(err or "unknown error"),
                    ),
                )
            )
            continue

        exports_by_module[str(entry.module)] = all_literal.values

    return exports_by_module, tuple(sorted(problems, key=lambda p: (str(p.path), int(p.lineno), str(p.module), str(p.reason))))


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    entrypoints, marker_problems = discover_public_api_entrypoints(_REPO_ROOT, tier=1)

    exports_by_module, export_problems = _collect_exports_or_problems(entrypoints, repo_root=_REPO_ROOT)
    problems = tuple(marker_problems) + tuple(export_problems)
    if problems:
        sys.stderr.write("[错误] 公共接口导出清单生成失败 ({} 个问题):\n".format(len(problems)))
        sys.stderr.write(_format_problems(problems, repo_root=_REPO_ROOT))
        sys.stderr.write("\n")
        return 1

    out: List[str] = []
    out.extend(_render_header())
    out.extend(_render_overview_table(entrypoints, exports_by_module))
    out.extend(_render_entrypoints_sections(entrypoints, exports_by_module))
    content = "\n".join(out).rstrip("\n") + "\n"

    out_path = _REPO_ROOT / ".tmp" / "public_api_exports_catalog.md"
    _write_text(out_path, content)
    sys.stdout.write("已写入 {}\n".format(_as_relpath(out_path, repo_root=_REPO_ROOT)))
    return 0


_REPO_ROOT = repo_root_for_script(Path(__file__))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
