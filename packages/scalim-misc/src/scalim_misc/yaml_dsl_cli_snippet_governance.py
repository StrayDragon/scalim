from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence, Tuple

if TYPE_CHECKING:
    from pathlib import Path

from .yaml_dsl_cli_reference_md import (
    DOCS_CLI_MIN_COMMANDS_BEGIN,
    DOCS_CLI_MIN_COMMANDS_END,
    SKILL_CLI_MIN_COMMANDS_BEGIN,
    SKILL_CLI_MIN_COMMANDS_END,
    WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
    WORKFLOW_CLI_MIN_COMMANDS_END,
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _strip_autogen_blocks(text: str) -> str:
    """Return text outside all `BEGIN/END AUTOGEN:*` blocks.

    The governance rule only forbids copyable CLI snippets outside injected blocks.
    """
    outside_lines: List[str] = []
    in_autogen_block = False
    for line in text.splitlines():
        if "<!-- BEGIN AUTOGEN:" in line:
            in_autogen_block = True
        if not in_autogen_block:
            outside_lines.append(line)
        if "<!-- END AUTOGEN:" in line:
            in_autogen_block = False
    return "\n".join(outside_lines)


def _missing_marker_errors(path: Path, *, begin_marker: str, end_marker: str) -> List[str]:
    errors: List[str] = []
    text = _read_text(path)
    if begin_marker not in text:
        errors.append("missing required marker in {}: {}".format(path, begin_marker))
    if end_marker not in text:
        errors.append("missing required marker in {}: {}".format(path, end_marker))
    return errors


def _forbidden_snippet_errors(path: Path, *, forbidden_prefixes: Sequence[str]) -> List[str]:
    text = _read_text(path)
    outside = _strip_autogen_blocks(text)
    errors: List[str] = []
    for prefix in forbidden_prefixes:
        if prefix in outside:
            errors.append("hand-written CLI snippet outside injected blocks in {}: {!r}".format(path, prefix))
    return errors


def check_yaml_dsl_cli_snippet_governance(repo_root: Path) -> List[str]:
    """Fail-fast governance gate for copyable YAML DSL CLI/LSP snippets.

    Rules (MVP scope):
    - required markers MUST exist
    - forbidden copyable command prefixes MUST NOT appear outside injected blocks
    """
    forbidden_prefixes: Tuple[str, ...] = (
        "uv run scalim-cli yaml-dsl",
        "uvx scalim-cli yaml-dsl",
        'uvx --from "scalim[cli]" scalim-cli yaml-dsl',
        'uvx --from "scalim-cli" scalim-cli yaml-dsl',
    )

    targets = [
        (
            repo_root / "docs" / "doc" / "yaml-dsl" / "workflow.md",
            WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
            WORKFLOW_CLI_MIN_COMMANDS_END,
            "just gen-docs",
        ),
        (
            repo_root / "docs" / "doc" / "yaml-dsl" / "agent-skill.md",
            DOCS_CLI_MIN_COMMANDS_BEGIN,
            DOCS_CLI_MIN_COMMANDS_END,
            "just gen-docs",
        ),
        (
            repo_root / "artifacts" / "skills" / "scalim-yaml-dsl" / "SKILL.md",
            SKILL_CLI_MIN_COMMANDS_BEGIN,
            SKILL_CLI_MIN_COMMANDS_END,
            "just gen-agent-skill",
        ),
    ]

    errors: List[str] = []
    for path, begin_marker, end_marker, fix_cmd in targets:
        if not path.exists():
            errors.append("missing file: {}".format(path))
            continue

        target_errors: List[str] = []
        target_errors.extend(_missing_marker_errors(path, begin_marker=begin_marker, end_marker=end_marker))
        target_errors.extend(_forbidden_snippet_errors(path, forbidden_prefixes=forbidden_prefixes))
        if target_errors:
            # Keep fix hints close to the offending file for fast iteration.
            target_errors.append("Fix hint: run `{}` and avoid hand-writing snippets outside AUTOGEN blocks.".format(fix_cmd))
            errors.extend(target_errors)

    return errors
