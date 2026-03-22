import argparse
import json
from pathlib import Path

import scalim.cli.yaml_dsl as yaml_dsl_cli
import yaml

from scalim_misc import agent_skill_gen


def _validate_args(path: Path, *, json_output: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        strict=True,
        json=json_output,
        verbose=False,
    )


def _schema_validate_args(path: Path, *, json_output: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        strict=True,
        json=json_output,
        verbose=False,
    )


def test_build_generates_generated_references_only(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    manifest = agent_skill_gen.build_skill(repo_root, output_root)

    skill_dir = output_root / agent_skill_gen.SKILL_NAME
    assert agent_skill_gen.list_files(skill_dir) == [
        "references/generated/cli-lsp-reference.gen.md",
        "references/generated/example-full/ecommerce_report.gen.yaml",
        "references/generated/example-full/ecommerce_report_fragments.yaml",
        "references/generated/yaml-dsl-upgrades.gen.md",
        "references/syntax-catalog.gen.md",
    ]

    manifest_path = agent_skill_gen.build_manifest_path(output_root)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["outputs"] == manifest["outputs"]
    assert [item["path"] for item in payload["outputs"]] == [
        "references/generated/cli-lsp-reference.gen.md",
        "references/generated/example-full/ecommerce_report.gen.yaml",
        "references/generated/example-full/ecommerce_report_fragments.yaml",
        "references/generated/yaml-dsl-upgrades.gen.md",
        "references/syntax-catalog.gen.md",
    ]
    assert "path_normalization" not in payload


def test_build_preserves_manual_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"
    skill_dir = output_root / agent_skill_gen.SKILL_NAME

    skill_md = skill_dir / "SKILL.md"
    task_ref = skill_dir / "references" / "task-authoring.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    task_ref.parent.mkdir(parents=True, exist_ok=True)
    openai_yaml.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text("manual skill\n", encoding="utf-8")
    task_ref.write_text("manual reference\n", encoding="utf-8")
    openai_yaml.write_text("interface:\n  display_name: manual\n", encoding="utf-8")

    agent_skill_gen.build_skill(repo_root, output_root)

    assert skill_md.read_text(encoding="utf-8") == "manual skill\n"
    assert task_ref.read_text(encoding="utf-8") == "manual reference\n"
    assert openai_yaml.read_text(encoding="utf-8") == "interface:\n  display_name: manual\n"


def test_build_removes_stale_generated_files_only(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"
    skill_dir = output_root / agent_skill_gen.SKILL_NAME

    stale_generated = skill_dir / "references" / "generated" / "stale.md"
    stale_gen_md = skill_dir / "references" / "stale.gen.md"
    manual_ref = skill_dir / "references" / "task-authoring.md"
    stale_generated.parent.mkdir(parents=True, exist_ok=True)
    manual_ref.parent.mkdir(parents=True, exist_ok=True)
    stale_generated.write_text("stale\n", encoding="utf-8")
    stale_gen_md.write_text("stale gen\n", encoding="utf-8")
    manual_ref.write_text("manual stays\n", encoding="utf-8")

    agent_skill_gen.build_skill(repo_root, output_root)

    assert not stale_generated.exists()
    assert not stale_gen_md.exists()
    assert manual_ref.read_text(encoding="utf-8") == "manual stays\n"


def test_validate_ignores_manual_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    agent_skill_gen.build_skill(repo_root, output_root)
    skill_dir = output_root / agent_skill_gen.SKILL_NAME
    (skill_dir / "SKILL.md").write_text("manual drift is allowed\n", encoding="utf-8")
    (skill_dir / "references" / "task-validate-debug.md").parent.mkdir(parents=True, exist_ok=True)
    (skill_dir / "references" / "task-validate-debug.md").write_text("manual drift is allowed\n", encoding="utf-8")

    assert agent_skill_gen.validate_skill(repo_root, output_root) is True


def test_validate_detects_generated_drift(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    agent_skill_gen.build_skill(repo_root, output_root)
    generated_path = output_root / agent_skill_gen.SKILL_NAME / "references" / "syntax-catalog.gen.md"
    generated_path.write_text("broken\n", encoding="utf-8")

    assert agent_skill_gen.validate_skill(repo_root, output_root) is False


def test_generated_example_passes_cli_validate_and_schema_validate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    agent_skill_gen.build_skill(repo_root, output_root)
    yaml_path = output_root / agent_skill_gen.SKILL_NAME / "references" / "generated" / "example-full" / "ecommerce_report.gen.yaml"

    assert yaml_dsl_cli._run_schema_validate(_schema_validate_args(yaml_path, json_output=False)) == 0
    assert yaml_dsl_cli._run_validate(_validate_args(yaml_path, json_output=False)) == 0


def test_generated_example_omits_yaml_lsp_header(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    agent_skill_gen.build_skill(repo_root, output_root)
    yaml_path = output_root / agent_skill_gen.SKILL_NAME / "references" / "generated" / "example-full" / "ecommerce_report.gen.yaml"

    first_line = yaml_path.read_text(encoding="utf-8").splitlines()[0]
    assert not first_line.startswith("# yaml-language-server: $schema=")
    assert not first_line.startswith("# $schema:")


def test_generated_cli_reference_has_required_commands_and_paths(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    agent_skill_gen.build_skill(repo_root, output_root)
    cli_ref = (output_root / agent_skill_gen.SKILL_NAME / "references" / "generated" / "cli-lsp-reference.gen.md").read_text(
        encoding="utf-8"
    )

    assert "src/scalim/cli/yaml_dsl.py" in cli_ref
    assert "src/scalim/_project_constants.py" in cli_ref
    assert "src/scalim/dsl/by_yaml/schema/demand.gen.json" in cli_ref
    assert "src/scalim/dsl/by_yaml/schema/workflow.gen.json" in cli_ref
    assert "uv run scalim-cli yaml-dsl validate <file.yaml>" in cli_ref
    assert "uv run scalim-cli yaml-dsl schema validate <file.yaml>" in cli_ref
    assert "uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>" in cli_ref
    assert 'uvx --from "scalim[cli]" scalim-cli yaml-dsl validate <file.yaml>' in cli_ref
    assert 'uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate <file.yaml>' in cli_ref
    assert "uv run scalim-cli yaml-dsl schema path" in cli_ref
    assert 'uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path' in cli_ref
    assert "uv run scalim-cli yaml-dsl upsert-lsp-comment" in cli_ref
    assert "--comment-style all" in cli_ref
    assert "--type workflow" in cli_ref
    assert "Canonical example: 故意不写 schema 头" in cli_ref
    assert "# yaml-language-server: $schema=.../demand.gen.json" in cli_ref
    assert "# $schema: .../demand.gen.json" in cli_ref
    assert "# yaml-language-server: $schema=.../workflow.gen.json" in cli_ref
    assert "# $schema: .../workflow.gen.json" in cli_ref
    assert "python -c" in cli_ref
    assert ".venv/..." in cli_ref


def test_generated_cli_reference_does_not_leak_output_root_or_site_packages_path(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "custom" / "skills-root"

    agent_skill_gen.build_skill(repo_root, output_root)
    skill_dir = output_root / agent_skill_gen.SKILL_NAME
    cli_ref = (skill_dir / "references" / "generated" / "cli-lsp-reference.gen.md").read_text(encoding="utf-8")

    assert str(output_root).replace("\\", "/") not in cli_ref
    assert "site-packages/scalim" not in cli_ref


def test_generated_syntax_catalog_covers_top_level_and_definitions(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "out"

    agent_skill_gen.build_skill(repo_root, output_root)
    catalog = (output_root / agent_skill_gen.SKILL_NAME / "references" / "syntax-catalog.gen.md").read_text(encoding="utf-8")

    assert "## Top-Level Fields" in catalog
    assert "## Definitions" in catalog
    assert "### `main_source`" in catalog
    assert "### `outputs`" in catalog
    assert "### `observability`" in catalog
    assert "### `source`" in catalog
    assert "## Workflow YAML (Generated)" in catalog
    assert "workflow.runs[*].depends_on" in catalog
    assert "workflow.runs[*].init_vars" in catalog
    assert "workflow.runs[*].writes" in catalog
    assert "workflow.runs[*].write_to" not in catalog
    assert "write_to" not in catalog
    assert "workflow.options.ctx" in catalog
    assert "workflow.resources.sheetbooks" in catalog


def test_manual_skill_contract_matches_generated_layout() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = repo_root / "artifacts" / "skills" / agent_skill_gen.SKILL_NAME
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"

    assert skill_md.exists()
    assert openai_yaml.exists()

    text = skill_md.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    frontmatter = yaml.safe_load(parts[1])
    agent_skill_gen.validate_frontmatter(frontmatter["name"], frontmatter["description"])

    assert "references/task-authoring.md" in text
    assert "references/task-workflow-authoring.md" in text
    assert "references/task-upgrade-legacy.md" in text
    assert "references/task-validate-debug.md" in text
    assert "references/task-workflow-validate-debug.md" in text
    assert "references/task-report-migration-playbook.md" in text
    assert "references/syntax-catalog.gen.md" in text
    assert "references/generated/cli-lsp-reference.gen.md" in text
    assert "references/generated/example-full/ecommerce_report.gen.yaml" in text
    assert "uv run scalim-cli yaml-dsl validate <demand.yaml>" in text
    assert "uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>" in text
    assert 'uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate <file.yaml>' in text
    assert 'uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path' in text
    assert "完整 canonical example 故意不带头部" in text

    assert not (skill_dir / "references" / "dsl-reference.md").exists()
    assert not (skill_dir / "references" / "example-full").exists()
    assert not (skill_dir / "references" / "task-upgrade-v3.md").exists()
