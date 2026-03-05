from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source_path = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema" / "demand.gen.json"

    targets = [
        repo_root / "frontend" / "scalim-yaml-dsl-editor" / "public" / "schema" / "demand.gen.json",
        repo_root / "frontend" / "scalim-yaml-dsl-editor" / "src" / "schema" / "demand.gen.json",
    ]

    text = source_path.read_text(encoding="utf-8")
    for target_path in targets:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
