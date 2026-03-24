from pathlib import Path

from scalim_misc.cli_docs import build_yaml_dsl_command_docs
from scalim_misc.yaml_dsl_cli_reference_md import render_yaml_dsl_cli_reference_markdown


def test_build_yaml_dsl_command_docs_includes_upsert_lsp_comment() -> None:
    docs = build_yaml_dsl_command_docs()
    tokens = [tuple(item["tokens"]) for item in docs]
    assert ("yaml-dsl", "upsert-lsp-comment") in tokens


def test_yaml_dsl_cli_reference_renderer_is_deterministic() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    command_docs = build_yaml_dsl_command_docs()

    a = render_yaml_dsl_cli_reference_markdown(repo_root, command_docs, generated_by="test")
    b = render_yaml_dsl_cli_reference_markdown(repo_root, command_docs, generated_by="test")
    assert a == b
