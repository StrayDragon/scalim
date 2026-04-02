import argparse
from pathlib import Path
from typing import Optional

import scalim.cli.yaml_dsl as yaml_dsl
from scalim.cli import yaml_dsl_lsp


def _upsert_args(
    *paths: Path,
    schema_type: str = "demand",
    schema_path: Optional[str] = None,
    comment_style: str = "all",
) -> argparse.Namespace:
    return argparse.Namespace(
        schema_type=schema_type,
        schema_path=schema_path,
        comment_style=comment_style,
        paths=list(paths),
    )


def test_upsert_lsp_comment_inserts_both_modelines_by_default(tmp_path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text("name: demo\n", encoding="utf-8")

    code = yaml_dsl._run_upsert_lsp_comment(_upsert_args(yaml_path))
    assert code == 0

    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# yaml-language-server: $schema=")
    assert lines[0].endswith("demand.gen.json")
    assert lines[1].startswith("# $schema: ")
    assert lines[1].endswith("demand.gen.json")


def test_upsert_lsp_comment_comment_style_jetbrains_removes_yaml_language_server_modeline_and_is_idempotent(tmp_path) -> None:
    yaml_path = tmp_path / "legacy.yaml"
    yaml_path.write_text(
        "# yaml-language-server: $schema=/wrong/path/demand.gen.json\nname: demo\n",
        encoding="utf-8",
    )

    code = yaml_dsl._run_upsert_lsp_comment(
        _upsert_args(
            yaml_path,
            schema_path="http://localhost:62831",
            comment_style="jetbrains",
        )
    )
    assert code == 0

    content = yaml_path.read_text(encoding="utf-8")
    assert content.splitlines()[0] == "# $schema: http://localhost:62831/demand.gen.json"
    assert "yaml-language-server" not in content

    code = yaml_dsl._run_upsert_lsp_comment(
        _upsert_args(
            yaml_path,
            schema_path="http://localhost:62831",
            comment_style="jetbrains",
        )
    )
    assert code == 0
    assert yaml_path.read_text(encoding="utf-8") == content


def test_upsert_lsp_comment_comment_style_redhat_removes_intellij_modeline_and_is_idempotent(tmp_path) -> None:
    yaml_path = tmp_path / "legacy.yaml"
    yaml_path.write_text(
        "# $schema: /wrong/path/demand.gen.json\nname: demo\n",
        encoding="utf-8",
    )

    code = yaml_dsl._run_upsert_lsp_comment(
        _upsert_args(
            yaml_path,
            schema_path="http://localhost:62831",
            comment_style="redhat",
        )
    )
    assert code == 0

    content = yaml_path.read_text(encoding="utf-8")
    assert content.splitlines()[0] == "# yaml-language-server: $schema=http://localhost:62831/demand.gen.json"
    assert "# $schema:" not in content

    code = yaml_dsl._run_upsert_lsp_comment(
        _upsert_args(
            yaml_path,
            schema_path="http://localhost:62831",
            comment_style="redhat",
        )
    )
    assert code == 0
    assert yaml_path.read_text(encoding="utf-8") == content


def test_upsert_lsp_comment_inserts_after_document_start_marker(tmp_path) -> None:
    yaml_path = tmp_path / "doc.yaml"
    yaml_path.write_text("---\nname: demo\n", encoding="utf-8")

    code = yaml_dsl._run_upsert_lsp_comment(_upsert_args(yaml_path))
    assert code == 0

    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    assert lines[1].startswith("# yaml-language-server: $schema=")
    assert lines[2].startswith("# $schema: ")


def test_resolve_schema_ref_supports_url_base_dir_base_and_full_json(tmp_path) -> None:
    assert yaml_dsl_lsp.resolve_schema_ref("workflow", "http://localhost:62831") == "http://localhost:62831/workflow.gen.json"

    base_dir = tmp_path / "schema"
    assert yaml_dsl_lsp.resolve_schema_ref("demand", str(base_dir)) == str(base_dir / "demand.gen.json")

    assert yaml_dsl_lsp.resolve_schema_ref("demand", "http://example.invalid/custom.json") == "http://example.invalid/custom.json"
