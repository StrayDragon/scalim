from pathlib import Path

from scalim_yaml_dsl_lsp.core import YAML_DSL_KIND_DEMAND, build_yaml_dsl_editor_effective_view


def test_effective_view_import_expansion_failure_still_collects_in_file_fields(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create a fragment *outside* allowed roots to trigger the allowed-roots guardrail.
    outside_fragment = tmp_path / "frag.yaml"
    outside_fragment.write_text("fields: {b: {compute: '1'}}\n", encoding="utf-8")

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            "  frags: ../frag.yaml",
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {a: {}}",
            "sources: {}",
            "fields:",
            "  $import: frags.fields",
            "outputs: []",
            "",
        ]
    )

    view = build_yaml_dsl_editor_effective_view(
        yaml_text,
        yaml_path=yaml_path,
        yaml_kind=YAML_DSL_KIND_DEMAND,
        allowed_yaml_roots=(Path(workspace),),
        scalim_yaml_override=None,
        project_root_override=workspace,
    )

    assert view.yaml_kind == YAML_DSL_KIND_DEMAND
    # Even when imports expansion fails, editor semantics should still be useful for in-file fields.
    assert "a" in set(view.field_ids)
    assert "a" in view.field_definitions_by_id
    assert view.import_fragment_files == ()
    assert view.warnings
    assert any("imports expansion failed" in w for w in view.warnings)
