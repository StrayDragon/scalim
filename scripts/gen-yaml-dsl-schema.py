import re
from pathlib import Path

from scalim.dsl.by_yaml.schema_dsl.builder import write_demand_schema
from scalim.dsl.by_yaml.schema_dsl.doc_texts import SOURCE_FIELD_EXTRACT_MD


USER_GUIDE_SOURCE_FIELD_EXTRACT_BEGIN = "<!-- BEGIN SCALIM-GEN:yaml-dsl-source-field-extract -->"
USER_GUIDE_SOURCE_FIELD_EXTRACT_END = "<!-- END SCALIM-GEN:yaml-dsl-source-field-extract -->"


def _replace_markdown_region(text: str, begin_marker: str, end_marker: str, new_body: str) -> str:
    new_block = begin_marker + "\n" + new_body.rstrip() + "\n" + end_marker
    pattern = re.compile(re.escape(begin_marker) + r"\n.*?\n" + re.escape(end_marker), re.DOTALL)
    replaced, count = pattern.subn(new_block, text, count=1)
    if count != 1:
        raise RuntimeError("无法替换 `Markdown` 区块: 期望标记精确匹配 1 次,但未满足: {} ... {}".format(begin_marker, end_marker))
    return replaced


def sync_yaml_dsl_user_guide(repo_root: Path) -> None:
    user_guide = repo_root / "docs" / "doc" / "yaml-dsl" / "user-guide.md"
    if not user_guide.exists():
        raise FileNotFoundError(str(user_guide))

    original = user_guide.read_text(encoding="utf-8")
    updated = _replace_markdown_region(
        original,
        begin_marker=USER_GUIDE_SOURCE_FIELD_EXTRACT_BEGIN,
        end_marker=USER_GUIDE_SOURCE_FIELD_EXTRACT_END,
        new_body=SOURCE_FIELD_EXTRACT_MD,
    )
    if updated != original:
        user_guide.write_text(updated, encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    output_path = schema_dir / "demand.gen.json"

    write_demand_schema(output_path)
    sync_yaml_dsl_user_guide(repo_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
