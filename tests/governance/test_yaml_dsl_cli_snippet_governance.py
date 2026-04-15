from pathlib import Path

from scalim_misc.yaml_dsl_cli_reference_md import (
    DOCS_CLI_MIN_COMMANDS_BEGIN,
    DOCS_CLI_MIN_COMMANDS_END,
    SKILL_CLI_MIN_COMMANDS_BEGIN,
    SKILL_CLI_MIN_COMMANDS_END,
    WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
    WORKFLOW_CLI_MIN_COMMANDS_END,
)
from scalim_misc.yaml_dsl_cli_snippet_governance import check_yaml_dsl_cli_snippet_governance


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_yaml_dsl_cli_governance_fails_when_marker_missing(tmp_path: Path) -> None:
    repo_root = tmp_path

    _write(repo_root / "docs" / "doc" / "yaml-dsl" / "workflow.md", "# workflow\n")
    _write(repo_root / "docs" / "doc" / "yaml-dsl" / "agent-skill.md", "# agent\n")
    _write(repo_root / "artifacts" / "skills" / "scalim-yaml-dsl" / "SKILL.md", "# skill\n")

    errors = check_yaml_dsl_cli_snippet_governance(repo_root)
    assert any("missing required marker" in item for item in errors)


def test_yaml_dsl_cli_governance_fails_on_hand_written_snippet_outside_markers(tmp_path: Path) -> None:
    repo_root = tmp_path

    workflow = "\n".join(
        [
            "# workflow",
            "",
            WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
            "```bash",
            "uv run scalim-cli yaml-dsl validate --type workflow path/to/workflow.yaml",
            "```",
            WORKFLOW_CLI_MIN_COMMANDS_END,
            "",
            "uv run scalim-cli yaml-dsl validate --type workflow path/to/workflow.yaml",
            "",
        ]
    )
    agent = "\n".join(
        [
            "# agent",
            "",
            DOCS_CLI_MIN_COMMANDS_BEGIN,
            "- `uv run scalim-cli yaml-dsl validate path/to/demand.yaml`",
            DOCS_CLI_MIN_COMMANDS_END,
            "",
        ]
    )
    skill = "\n".join(
        [
            "# skill",
            "",
            SKILL_CLI_MIN_COMMANDS_BEGIN,
            "- `uv run scalim-cli yaml-dsl validate <demand.yaml>`",
            SKILL_CLI_MIN_COMMANDS_END,
            "",
        ]
    )

    _write(repo_root / "docs" / "doc" / "yaml-dsl" / "workflow.md", workflow)
    _write(repo_root / "docs" / "doc" / "yaml-dsl" / "agent-skill.md", agent)
    _write(repo_root / "artifacts" / "skills" / "scalim-yaml-dsl" / "SKILL.md", skill)

    errors = check_yaml_dsl_cli_snippet_governance(repo_root)
    assert any("hand-written CLI snippet outside injected blocks" in item for item in errors)


def test_yaml_dsl_cli_governance_passes_when_snippets_are_only_inside_markers(tmp_path: Path) -> None:
    repo_root = tmp_path

    workflow = "\n".join(
        [
            "# workflow",
            "",
            WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
            "```bash",
            "uv run scalim-cli yaml-dsl validate --type workflow path/to/workflow.yaml",
            "```",
            WORKFLOW_CLI_MIN_COMMANDS_END,
            "",
        ]
    )
    agent = "\n".join(
        [
            "# agent",
            "",
            DOCS_CLI_MIN_COMMANDS_BEGIN,
            "- demand: `uv run scalim-cli yaml-dsl validate path/to/demand.yaml`",
            "- external: `uvx scalim-cli yaml-dsl validate path/to/config.yaml`",
            DOCS_CLI_MIN_COMMANDS_END,
            "",
        ]
    )
    skill = "\n".join(
        [
            "# skill",
            "",
            SKILL_CLI_MIN_COMMANDS_BEGIN,
            "- demand: `uv run scalim-cli yaml-dsl validate <demand.yaml>`",
            "- external: `uvx scalim-cli yaml-dsl validate <file.yaml>`",
            SKILL_CLI_MIN_COMMANDS_END,
            "",
        ]
    )

    _write(repo_root / "docs" / "doc" / "yaml-dsl" / "workflow.md", workflow)
    _write(repo_root / "docs" / "doc" / "yaml-dsl" / "agent-skill.md", agent)
    _write(repo_root / "artifacts" / "skills" / "scalim-yaml-dsl" / "SKILL.md", skill)

    errors = check_yaml_dsl_cli_snippet_governance(repo_root)
    assert errors == []
