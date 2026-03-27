#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""生成 `notebooks/marimo/` 的 `deterministic` 覆盖报告。

用于替代手工维护的 `notebooks/marimo/coverage_matrix.md`。
该报告从以下来源推导并生成:
- `notebooks/marimo/**` 的 `notebooks` 文件树(教学入口 + `SSOT` 执行入口)
- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/**` 的 `YAML` 固定示例(真值)
- `notebooks/marimo/example_public_api_suite/**` 的 `public API` 覆盖套件
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class _Row:
    kind: str
    item_id: str
    notebook: Optional[Path]
    ssot: Optional[Path]
    gate: Optional[Path]
    pytest: Optional[Path]
    ok: bool
    notes: str = ""


def _diff(a: str, b: str, a_name: str, b_name: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile=a_name,
            tofile=b_name,
            lineterm="",
        )
    )


def _write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _check_exact(path: Path, expected: str) -> Tuple[bool, str]:
    got = path.read_text(encoding="utf-8") if path.exists() else ""
    if got == expected:
        return True, ""
    return False, _diff(got, expected, str(path), str(path) + " (expected)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_on_syspath(root: Path) -> None:
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _parse_yaml_schema_header(path: Path) -> Tuple[bool, str]:
    """检查 `# yaml-language-server: $schema=...` 指向的 `schema` 文件是否存在。"""
    try:
        head = path.read_text(encoding="utf-8").splitlines()[:5]
    except OSError as exc:
        return False, "read_failed: {}".format(exc)

    schema_line = next((line for line in head if "$schema=" in line), "")
    m = re.search(r"\$schema=(\S+)", schema_line)
    if not m:
        return False, "missing_schema_header"

    rel = m.group(1).strip()
    schema_path = (path.parent / rel).resolve()
    if not schema_path.exists():
        return False, "schema_missing: {}".format(rel)
    return True, "schema_ok: {}".format(rel)


def _find_demo_notebook_for_chapter(chapters_dir: Path, chapter_id: str) -> Optional[Path]:
    matches = sorted([p for p in chapters_dir.glob("*.py") if p.name.endswith("{}.py".format(chapter_id))])
    return matches[0] if matches else None


def _load_demo_chapter_ids() -> List[str]:
    from notebooks.marimo.demo_big_data_report.chapters.registry import all_chapter_ids  # noqa: PLC0415

    return list(all_chapter_ids())


def _load_public_api_chapter_ids() -> List[str]:
    from notebooks.marimo.example_public_api_suite.chapters.registry import all_chapter_ids  # noqa: PLC0415

    return list(all_chapter_ids())


def _collect_rows(root: Path) -> Tuple[List[_Row], List[str]]:
    warnings: List[str] = []
    rows: List[_Row] = []

    notebooks_root = root / "notebooks" / "marimo"
    demo_root = notebooks_root / "demo_big_data_report"
    demo_chapters_dir = demo_root / "chapters"
    public_api_root = notebooks_root / "example_public_api_suite"
    public_api_chapters_dir = public_api_root / "chapters"

    gate_runner = notebooks_root / "run_examples.py"
    pytest_demo_chapters = root / "tests" / "test_demo_big_data_report_chapters.py"
    pytest_public_api = root / "tests" / "test_example_public_api_suite.py"

    # --- 入口页 ---
    hubs = [
        ("hub", "notebooks/marimo/index.py", notebooks_root / "index.py"),
        ("hub", "demo_big_data_report/demo_main.py", demo_root / "demo_main.py"),
        ("hub", "example_public_api_suite/demo_main.py", public_api_root / "demo_main.py"),
    ]
    for kind, item_id, path in hubs:
        ok = path.exists()
        rows.append(
            _Row(
                kind=kind,
                item_id=item_id,
                notebook=path if ok else None,
                ssot=None,
                gate=gate_runner if gate_runner.exists() else None,
                pytest=None,
                ok=ok,
                notes="" if ok else "missing",
            )
        )

    # --- YAML 固定示例 ---
    demand_yaml = demo_root / "by_yaml_dsl" / "ecommerce_report.yaml"
    fragments_yaml = demo_root / "by_yaml_dsl" / "ecommerce_report_fragments.yaml"
    workflow_yaml = demo_root / "by_yaml_dsl" / "workflow_fixture.yaml"

    for item_id, path in [
        ("canonical_yaml/demand", demand_yaml),
        ("canonical_yaml/fragments", fragments_yaml),
        ("canonical_yaml/workflow", workflow_yaml),
    ]:
        ok = path.exists()
        note = ""
        if ok and path.suffix == ".yaml" and item_id != "canonical_yaml/fragments":
            schema_ok, schema_note = _parse_yaml_schema_header(path)
            ok = ok and schema_ok
            note = schema_note
        if ok and item_id == "canonical_yaml/fragments":
            note = "schema_header: (optional)"
        rows.append(
            _Row(
                kind="fixture",
                item_id=item_id,
                notebook=path if path.exists() else None,
                ssot=None,
                gate=gate_runner if gate_runner.exists() else None,
                pytest=None,
                ok=ok,
                notes=note if note else ("missing" if not ok else ""),
            )
        )

    # --- 主线章节 ---
    chapter_ids = _load_demo_chapter_ids()
    for chapter_id in chapter_ids:
        notebook = _find_demo_notebook_for_chapter(demo_chapters_dir, chapter_id) if demo_chapters_dir.exists() else None
        ssot = notebook
        pytest_path = pytest_demo_chapters
        ok = bool(notebook and gate_runner.exists())
        note_parts: List[str] = []
        if not notebook:
            note_parts.append("missing_notebook")
        if not gate_runner.exists():
            note_parts.append("missing_gate")
        rows.append(
            _Row(
                kind="chapter",
                item_id="demo_big_data_report/{}".format(chapter_id),
                notebook=notebook,
                ssot=ssot,
                gate=gate_runner if gate_runner.exists() else None,
                pytest=pytest_path if pytest_path.exists() else None,
                ok=ok,
                notes=",".join(note_parts),
            )
        )

    # --- `public API` 套件章节 ---
    chapter_ids = _load_public_api_chapter_ids()
    for chapter_id in chapter_ids:
        notebook = _find_demo_notebook_for_chapter(public_api_chapters_dir, chapter_id) if public_api_chapters_dir.exists() else None
        ssot = notebook
        pytest_path = pytest_public_api
        ok = bool(notebook and gate_runner.exists())
        note_parts = []
        if not notebook:
            note_parts.append("missing_notebook")
        if not gate_runner.exists():
            note_parts.append("missing_gate")
        rows.append(
            _Row(
                kind="chapter",
                item_id="example_public_api_suite/{}".format(chapter_id),
                notebook=notebook,
                ssot=ssot,
                gate=gate_runner if gate_runner.exists() else None,
                pytest=pytest_path if pytest_path.exists() else None,
                ok=ok,
                notes=",".join(note_parts),
            )
        )

    if not gate_runner.exists():
        warnings.append("missing gate runner: {}".format(gate_runner))
    return rows, warnings


def _format_path(path: Optional[Path], *, root: Path) -> str:
    if not path:
        return "—"
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _markdown_report(root: Path, rows: Sequence[_Row], warnings: Sequence[str]) -> str:
    total = len(rows)
    ok_count = len([r for r in rows if r.ok])
    pct = 0.0 if total == 0 else (ok_count * 100.0 / total)

    lines: List[str] = []
    lines.append("# notebooks/marimo Coverage Report (generated)")
    lines.append("")
    lines.append("Generated by `scripts/gen-marimo-coverage.py`. Do not edit by hand.")
    lines.append("")
    lines.append("## Summary")
    lines.append("- Items: {}/{} ({:.1f}%) OK".format(ok_count, total, pct))
    if warnings:
        lines.append("- Warnings:")
        for w in warnings:
            lines.append("  - {}".format(w))
    lines.append("")

    lines.append("## Report")
    lines.append("| Kind | Item | Notebook | SSOT | Gate | Pytest | Status | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        status = "OK" if r.ok else "MISS"
        lines.append(
            "| {} | {} | `{}` | `{}` | `{}` | `{}` | {} | {} |".format(
                r.kind,
                r.item_id,
                _format_path(r.notebook, root=root),
                _format_path(r.ssot, root=root),
                _format_path(r.gate, root=root),
                _format_path(r.pytest, root=root),
                status,
                r.notes or "",
            )
        )
    lines.append("")

    lines.append("## How To Regenerate")
    lines.append("- `just gen-marimo-coverage`")
    lines.append("- or: `uv --preview-features extra-build-dependencies run python scripts/gen-marimo-coverage.py`")
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成 `notebooks/marimo/` 覆盖报告(SSOT)。")
    p.add_argument(
        "--output",
        help="输出路径(默认: notebooks/marimo/marimo_coverage.gen.md)。",
    )
    p.add_argument("--check", action="store_true", help="仅检查是否漂移; 不写文件。")
    return p.parse_args(list(argv or sys.argv[1:]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    root = _repo_root()
    _ensure_repo_on_syspath(root)

    rows, warnings = _collect_rows(root)
    content = _markdown_report(root, rows, warnings)

    output = Path(args.output) if args.output else root / "notebooks" / "marimo" / "marimo_coverage.gen.md"

    if args.check:
        ok, diff = _check_exact(output, content)
        if ok:
            print("通过: {}".format(output))
            return 0
        sys.stderr.write("检测到 `marimo` 覆盖报告漂移:\n\n{}\n".format(diff or "(无差异)"))
        sys.stderr.write("\n修复: 运行 `just gen-marimo-coverage`\n")
        return 1

    changed = _write_if_changed(output, content)
    verb = "已更新" if changed else "无需更新"
    print("{}: {}".format(verb, output))
    missing = [r for r in rows if not r.ok]
    if missing:
        sys.stderr.write("\n缺失项:\n")
        for r in missing[:20]:
            sys.stderr.write("- {} {}\n".format(r.kind, r.item_id))
        if len(missing) > 20:
            sys.stderr.write("- ... (还有 {} 项)\n".format(len(missing) - 20))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
