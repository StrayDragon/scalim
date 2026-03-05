from pathlib import Path

import pytest
import yaml

from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim_misc import agent_skill_gen


def test_path_normalization_external():
    repo_root = Path("/repo")
    text = "path: /tmp/secret.csv"
    normalized, mappings = agent_skill_gen.normalize_paths_in_text(text, repo_root)
    assert "$LOCAL_PATH/secret.csv" in normalized
    assert "external" in normalized
    assert mappings[0]["external"] is True


def test_example_priority_prefers_notebooks():
    notebook_examples = [
        agent_skill_gen.build_example("name: a\nmain_source:\nsources:\nfields:\n", "minimal"),
        agent_skill_gen.build_example("name: b\nmain_source:\nsources:\nfields:\nrelations:\n", "advanced"),
    ]
    test_examples = [agent_skill_gen.build_example("name: c\nmain_source:\nsources:\nfields:\n", None)]
    minimal, advanced = agent_skill_gen.select_examples(notebook_examples, test_examples)
    assert minimal["text"] == notebook_examples[0]["text"]
    assert advanced["text"] == notebook_examples[1]["text"]


def test_region_example_extraction(tmp_path):
    content = "\n".join(
        [
            "# region SCALIM-SKILL:minimal",
            "name: example",
            "main_source:",
            "sources:",
            "fields:",
            "# endregion",
            "",
        ]
    )
    path = tmp_path / "examples.md"
    path.write_text(content, encoding="utf-8")
    examples = agent_skill_gen.extract_skill_regions_from_text(path, content)
    assert examples[0]["tag"] == "minimal"


def test_build_requires_examples(tmp_path):
    repo_root = tmp_path / "repo"
    examples_root = repo_root / "notebooks" / "marimo" / "examples" / "demo_big_data_report"
    by_yaml_root = examples_root / "by_yaml_dsl"
    by_yaml_root.mkdir(parents=True)

    # Keep required files present, but intentionally do not provide SCALIM-SKILL regions.
    (examples_root / "README.md").write_text("", encoding="utf-8")
    (examples_root / "_loaders.py").write_text("", encoding="utf-8")
    (examples_root / "demo_a0_tutor.py").write_text("", encoding="utf-8")
    (by_yaml_root / "ecommerce_report.yaml").write_text("", encoding="utf-8")

    with pytest.raises(agent_skill_gen.GenerationError, match="缺少 minimal 示例"):
        agent_skill_gen.build_skill(repo_root, tmp_path / "out")


def test_region_examples_validate_against_schema():
    repo_root = Path(__file__).resolve().parents[1]
    examples, _ = agent_skill_gen.extract_yaml_examples_from_marked_files(repo_root / "notebooks" / "marimo" / "examples")
    if not examples:
        pytest.skip("No SCALIM-SKILL YAML examples found under notebooks/marimo/examples.")
    minimal, advanced = agent_skill_gen.select_examples(examples, [])
    agent_skill_gen.require_examples(minimal, advanced, examples, [])
    validator = ConfigValidator()
    for example in examples:
        config = yaml.safe_load(example["text"])
        validator.validate(config)


def test_example_full_yaml_validate_against_schema():
    repo_root = Path(__file__).resolve().parents[1]
    sections, _ = agent_skill_gen.extract_skill_sections_from_paths(
        [repo_root / "notebooks" / "marimo" / "examples" / "demo_big_data_report" / "by_yaml_dsl" / "ecommerce_report.yaml"]
    )
    yaml_text = agent_skill_gen.require_section(sections, "example-full", "yaml")
    validator = ConfigValidator()
    config = yaml.safe_load(yaml_text)
    validator.validate(config)
