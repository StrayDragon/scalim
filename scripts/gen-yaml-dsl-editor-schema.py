from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    demand_path = schema_dir / "demand.gen.json"
    workflow_path = schema_dir / "workflow.gen.json"

    targets = [
        (
            demand_path,
            repo_root / "frontend" / "scalim-yaml-dsl-editor" / "public" / "schema" / "demand.gen.json",
        ),
        (
            demand_path,
            repo_root / "frontend" / "scalim-yaml-dsl-editor" / "src" / "schema" / "demand.gen.json",
        ),
        (
            workflow_path,
            repo_root / "frontend" / "scalim-yaml-dsl-editor" / "public" / "schema" / "workflow.gen.json",
        ),
        (
            workflow_path,
            repo_root / "frontend" / "scalim-yaml-dsl-editor" / "src" / "schema" / "workflow.gen.json",
        ),
    ]

    for source_path, target_path in targets:
        text = source_path.read_text(encoding="utf-8")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
