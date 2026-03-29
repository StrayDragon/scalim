import marimo

import importlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scalim_misc.examples.public_api._coverage import check_public_all_coverage, coverage_to_details
from scalim_misc.examples.public_api._manifest import load_public_api_manifest
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch120_public_api_manifest_alignment"

_SCALIM_IMPORT_RE = re.compile(r"(?:\bfrom\s+(scalim(?:\.[A-Za-z0-9_]+)*)\s+import\b)|(?:\bimport\s+(scalim(?:\.[A-Za-z0-9_]+)*)\b)")


def _iter_chapter_files() -> List[Path]:
    chapters_dir = Path(__file__).resolve().parent
    paths = [p for p in chapters_dir.iterdir() if p.is_file() and p.suffix == ".py" and p.name != "registry.py"]
    return sorted(paths, key=lambda p: p.name)


def _scan_suite_imports(
    *,
    curated_entrypoints: Tuple[str, ...],
    internal_prefix_suggestions: Dict[str, str],
) -> List[str]:
    curated = set(curated_entrypoints)
    internal_tokens = tuple(sorted(k for k in internal_prefix_suggestions.keys() if k))

    violations: List[str] = []
    for path in _iter_chapter_files():
        rel = path.name
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.rstrip()

            for token in internal_tokens:
                if token in stripped:
                    violations.append("{}:{}: internal token={!r}".format(rel, lineno, token))

            match = _SCALIM_IMPORT_RE.search(stripped)
            if not match:
                continue
            module_name = match.group(1) or match.group(2) or ""
            module_name = str(module_name).strip()
            if not module_name:
                continue
            if module_name not in curated:
                violations.append("{}:{}: uncurated import: {}".format(rel, lineno, module_name))
    return violations


def run_public_api_manifest_alignment() -> ExampleResult:
    manifest = load_public_api_manifest(__file__)

    module_failures: List[Dict[str, Any]] = []
    for module_name, expected in manifest.stable_modules.items():
        mod = importlib.import_module(module_name)
        coverage = check_public_all_coverage(mod, covered=set(expected))
        if not coverage.ok:
            module_failures.append(coverage_to_details(coverage))

    suite_import_violations = _scan_suite_imports(
        curated_entrypoints=manifest.curated_entrypoints,
        internal_prefix_suggestions=dict(manifest.internal_prefix_suggestions),
    )

    passed = bool(not module_failures and not suite_import_violations)
    summary = "stable_modules={} module_failures={} suite_import_violations={}".format(
        len(manifest.stable_modules),
        len(module_failures),
        len(suite_import_violations),
    )
    details: Dict[str, Any] = {
        "manifest_path": str(manifest.path),
        "stable_modules": sorted(manifest.stable_modules.keys()),
        "module_failures": module_failures,
        "suite_import_violations": list(suite_import_violations),
    }
    if module_failures:
        summary = "{} (first: {})".format(summary, module_failures[0].get("module"))
    if suite_import_violations:
        summary = "{} (first: {})".format(summary, suite_import_violations[0])
    return ExampleResult(
        example_id=_EXAMPLE_ID,
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_manifest_alignment()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch120_public_api_manifest_alignment

        本章目标:
        - 约束 public API manifest 与运行时 `__all__` 精确一致
        - 约束 suite 中的 `scalim.*` 导入路径仅来自 manifest 的 curated entrypoints

        Gate:
        - `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_public_api_manifest_alignment()
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return


if __name__ == "__main__":
    app.run()
