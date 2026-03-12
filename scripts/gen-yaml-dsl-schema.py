from pathlib import Path

from scalim.dsl.by_yaml.schema_dsl.builder import write_demand_schema, write_workflow_schema
from scalim.dsl.by_yaml.schema_dsl.doc_texts import SOURCE_FIELD_EXTRACT_MD
from scalim_misc.markdown_inject import InjectBlockSpec, replace_markdown_injected_block


USER_GUIDE_SOURCE_FIELD_EXTRACT_BEGIN = "<!-- BEGIN AUTOGEN:yaml-dsl-source-field-extract -->"
USER_GUIDE_SOURCE_FIELD_EXTRACT_END = "<!-- END AUTOGEN:yaml-dsl-source-field-extract -->"


def sync_yaml_dsl_user_guide(repo_root: Path) -> None:
    user_guide = repo_root / "docs" / "doc" / "yaml-dsl" / "user-guide.md"
    if not user_guide.exists():
        raise FileNotFoundError(str(user_guide))

    original = user_guide.read_text(encoding="utf-8")
    updated = replace_markdown_injected_block(
        original,
        spec=InjectBlockSpec(
            begin_marker=USER_GUIDE_SOURCE_FIELD_EXTRACT_BEGIN,
            end_marker=USER_GUIDE_SOURCE_FIELD_EXTRACT_END,
            label=str(user_guide),
        ),
        content=SOURCE_FIELD_EXTRACT_MD,
    )
    if updated != original:
        user_guide.write_text(updated, encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    demand_path = schema_dir / "demand.gen.json"
    workflow_path = schema_dir / "workflow.gen.json"

    write_demand_schema(demand_path)
    write_workflow_schema(workflow_path)
    sync_yaml_dsl_user_guide(repo_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
