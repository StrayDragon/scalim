from pathlib import Path

from scalim_misc.cli_docs import build_yaml_dsl_command_docs
from scalim_misc.yaml_dsl_cli_reference_md import render_yaml_dsl_cli_reference_markdown
from tests.support.pathing import repo_root as _repo_root


def test_build_yaml_dsl_command_docs_includes_upsert_lsp_comment() -> None:
    docs = build_yaml_dsl_command_docs()
    tokens = [tuple(item["tokens"]) for item in docs]
    assert ("yaml-dsl", "upsert-lsp-comment") in tokens


def test_yaml_dsl_cli_reference_renderer_is_deterministic() -> None:
    repo_root = _repo_root()
    command_docs = build_yaml_dsl_command_docs()

    a = render_yaml_dsl_cli_reference_markdown(repo_root, command_docs, generated_by="test")
    b = render_yaml_dsl_cli_reference_markdown(repo_root, command_docs, generated_by="test")
    assert a == b


def test_build_yaml_dsl_command_docs_is_independent_of_terminal_width(monkeypatch) -> None:
    monkeypatch.setenv("COLUMNS", "60")
    narrow = build_yaml_dsl_command_docs()

    monkeypatch.setenv("COLUMNS", "140")
    wide = build_yaml_dsl_command_docs()

    assert narrow == wide
