# ruff: noqa: T201
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Pattern, Tuple


@dataclass(frozen=True)
class _Rule:
    name: str
    pattern: Pattern[str]
    message: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _git_ls_files(root: Path, pattern: str) -> List[str]:
    try:
        output = subprocess.check_output(["git", "-C", str(root), "ls-files", pattern], text=True)
    except Exception as exc:
        raise RuntimeError("failed to list markdown files via git: {}".format(exc)) from exc
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def _is_allowed_markdown(rel_posix: str) -> bool:
    # 迁移/历史区域允许保留旧写法(辅助作者升级或回溯)
    if rel_posix.startswith("artifacts/skills/scalim-yaml-dsl/references/upgrades/"):
        return True
    if rel_posix == "artifacts/skills/scalim-yaml-dsl/references/generated/yaml-dsl-upgrades.gen.md":
        return True
    if rel_posix.startswith("openspec/changes/archive/"):
        return True
    return False


def _rules() -> Tuple[_Rule, ...]:
    return (
        _Rule(
            name="legacy-workflow-writes",
            pattern=re.compile(r"workflow\.runs\[\*\]\.writes"),
            message="Removed workflow authoring surface: use `workflow.resources.books` + demand outputs `to/write` bindings.",
        ),
        _Rule(
            name="legacy-workflow-resources-groups",
            pattern=re.compile(r"workflow\.resources\.(workbooks|csvs|sheetbooks)\b"),
            message="Removed workflow authoring surface: use `workflow.resources.books`.",
        ),
        _Rule(
            name="legacy-writes-output",
            pattern=re.compile(r"writes\[\*\]\.output\b"),
            message="Removed workflow writes surface: use demand outputs `to/write` bindings (plus `resources.books.*.write_defaults`).",
        ),
        _Rule(
            name="legacy-write-to",
            pattern=re.compile(r"\bwrite_to\b"),
            message="Removed field: use demand outputs `to/write` bindings.",
        ),
        _Rule(
            name="legacy-sheetbook-loader-id",
            pattern=re.compile(r"workflow/sheetbook_sheet_rows"),
            message="Removed builtin callable id: use `^workflow/book_sheet_rows`.",
        ),
        _Rule(
            name="legacy-sheetbook-loader",
            pattern=re.compile(r"\bsheetbook_sheet_rows\b"),
            message="Removed loader: use `scalim.workflow.loaders:book_sheet_rows` / `^workflow/book_sheet_rows`.",
        ),
        _Rule(
            name="legacy-workbook-container-type",
            pattern=re.compile(r"container\.type:\s*workbook\b"),
            message="Removed `.xlsx` output authoring surface: use `resources.books` + outputs→book bindings.",
        ),
        _Rule(
            name="legacy-type-workbook",
            pattern=re.compile(r"(?<!container\.)\btype:\s*workbook\b"),
            message="Removed `.xlsx` output authoring surface: use `resources.books` + outputs→book bindings.",
        ),
        _Rule(
            name="legacy-writes-sheetbook-intent",
            pattern=re.compile(r"writes\[\*\]\.sheetbook_"),
            message="Removed workflow sheetbook intents: use `resources.books` + outputs `write`.",
        ),
        _Rule(
            name="legacy-writes-sheetbook-intent-inline",
            pattern=re.compile(r"writes\.sheetbook_"),
            message="Removed workflow sheetbook intents: use `resources.books` + outputs `write`.",
        ),
        _Rule(
            name="legacy-writes-workbook-intent-inline",
            pattern=re.compile(r"writes\.workbook_"),
            message="Removed workflow workbook intents: use `resources.books` + outputs `write`.",
        ),
    )


def _scan_markdown(path: Path, *, rel_posix: str, rules: Iterable[_Rule]) -> List[Tuple[int, _Rule, str]]:
    text = _read_text(path)
    hits: List[Tuple[int, _Rule, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule in rules:
            if rule.pattern.search(line):
                hits.append((lineno, rule, line.rstrip("\n")))
    return hits


def main() -> int:
    root = _repo_root()
    rules = _rules()
    markdown_files = _git_ls_files(root, "*.md")

    errors: List[str] = []
    for rel_posix in markdown_files:
        if _is_allowed_markdown(rel_posix):
            continue
        path = (root / rel_posix).resolve()
        if not path.exists():
            continue
        hits = _scan_markdown(path, rel_posix=rel_posix, rules=rules)
        for lineno, rule, line in hits:
            errors.append("{}:{}: {}: {}\n  hint: {}".format(rel_posix, lineno, rule.name, line.strip(), rule.message))

    if errors:
        sys.stderr.write("Markdown SSOT check failed: legacy authoring surfaces detected.\n")
        sys.stderr.write("Allowed exceptions: artifacts/skills/.../references/upgrades/, yaml-dsl-upgrades.gen.md, openspec/changes/archive/\n")
        sys.stderr.write("Violations:\n")
        for item in errors[:200]:
            sys.stderr.write("- {}\n".format(item))
        if len(errors) > 200:
            sys.stderr.write("... and {} more.\n".format(len(errors) - 200))
        sys.stderr.write("\nFix: update docs/specs to match current schema/runtime SSOT.\n")
        return 1

    sys.stdout.write("OK: Markdown SSOT check passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

