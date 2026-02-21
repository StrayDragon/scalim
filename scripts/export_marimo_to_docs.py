from __future__ import annotations

import argparse
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


def _to_output_path(src: Path, notebook_root: Path, docs_notebook_root: Path) -> Path:
    examples_root = notebook_root / "examples"
    try:
        rel = src.relative_to(examples_root)
    except ValueError:
        rel = src.relative_to(notebook_root)
    return (docs_notebook_root / rel).with_suffix(".html")


def export_all(*, include_code: bool, clean: bool) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    notebook_root = repo_root / "notebooks" / "marimo"
    docs_notebook_root = repo_root / "docs" / "notebooks"

    notebooks = _discover_notebooks(notebook_root)
    if not notebooks:
        print(f"[export-marimo] No marimo notebooks found under: {notebook_root}", file=sys.stderr)
        return

    if clean and docs_notebook_root.exists():
        for html in docs_notebook_root.rglob("*.html"):
            html.unlink()

    for src in notebooks:
        dst = _to_output_path(src, notebook_root, docs_notebook_root)
        dst.parent.mkdir(parents=True, exist_ok=True)

        cmd = [sys.executable, "-m", "marimo", "export", "html", str(src), "-o", str(dst)]
        if not include_code:
            cmd.append("--no-include-code")

        print(f"[export-marimo] {src.relative_to(repo_root)} -> {dst.relative_to(repo_root)}")
        subprocess.run(cmd, cwd=repo_root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export marimo notebooks to docs/notebooks for MkDocs/GitHub Pages.")
    parser.add_argument("--include-code", action="store_true", help="Include code in exported HTML (default: hide code).")
    parser.add_argument("--clean", action="store_true", help="Remove existing exported HTML first.")
    args = parser.parse_args()

    export_all(include_code=args.include_code, clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
