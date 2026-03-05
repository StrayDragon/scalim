from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _is_marimo_notebook(py_file: Path) -> bool:
    try:
        content = py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
    return "marimo.App" in content


def _discover_notebooks(notebook_root: Path) -> list[Path]:
    return sorted(p for p in notebook_root.rglob("*.py") if _is_marimo_notebook(p))


def _to_output_path(src: Path, *, notebook_root: Path, docs_notebook_root: Path) -> Path:
    examples_root = notebook_root / "examples"
    try:
        rel = src.relative_to(examples_root)
    except ValueError:
        rel = src.relative_to(notebook_root)
    return (docs_notebook_root / rel).with_suffix(".html")


def _detect_docs_dir(repo_root: Path) -> Path:
    """读取 `docs/zensical.toml` 的 `docs_dir`,失败时回退到 `docs/doc`."""
    zensical_toml = repo_root / "docs" / "zensical.toml"
    default = repo_root / "docs" / "doc"
    if not zensical_toml.exists():
        return default

    try:
        text = zensical_toml.read_text(encoding="utf-8")
    except Exception:
        return default

    m = re.search(r'^\s*docs_dir\s*=\s*"(.+?)"\s*$', text, flags=re.MULTILINE)
    if not m:
        return default

    raw = m.group(1).strip()
    if not raw:
        return default
    return (zensical_toml.parent / raw).resolve()


def export_all(*, include_code: bool, clean: bool) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    notebook_root = repo_root / "notebooks" / "marimo"
    docs_dir = _detect_docs_dir(repo_root)
    docs_notebook_root = docs_dir / "notebooks"
    legacy_docs_notebook_root = repo_root / "docs" / "notebooks"

    notebooks = _discover_notebooks(notebook_root)
    if not notebooks:
        print(f"【导出 `marimo`】未发现笔记本: {notebook_root}", file=sys.stderr)
        return

    if clean and docs_notebook_root.exists():
        for html in docs_notebook_root.rglob("*.html"):
            html.unlink()

    if clean and legacy_docs_notebook_root != docs_notebook_root and legacy_docs_notebook_root.exists():
        for html in legacy_docs_notebook_root.rglob("*.html"):
            html.unlink()
        for p in sorted(legacy_docs_notebook_root.rglob("*"), reverse=True):
            if not p.is_dir():
                continue
            try:
                p.rmdir()
            except OSError:
                pass

    for src in notebooks:
        dst = _to_output_path(src, notebook_root=notebook_root, docs_notebook_root=docs_notebook_root)
        dst.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "marimo",
            "export",
            "html",
            str(src),
            "-o",
            str(dst),
            "--force",
        ]
        if not include_code:
            cmd.append("--no-include-code")

        print(f"【导出 `marimo`】{src.relative_to(repo_root)} -> {dst.relative_to(repo_root)}")
        proc = subprocess.run(cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            proc.check_returncode()


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 marimo notebook 为 HTML,用于 Zensical/GitHub Pages.")
    parser.add_argument("--include-code", action="store_true", help="导出时包含源码(默认隐藏).")
    parser.add_argument("--clean", action="store_true", help="先清理已导出的 HTML.")
    args = parser.parse_args()

    export_all(include_code=args.include_code, clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
