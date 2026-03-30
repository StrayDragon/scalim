import argparse
from pathlib import Path
from typing import Iterable, Optional


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="同步 YAML DSL editor schema (`*.gen.json`) 并提供漂移检查.")
    p.add_argument("--check", action="store_true", help="仅检查漂移,不写入文件.")
    args = p.parse_args(list(argv) if argv is not None else None)

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

    if not args.check:
        for source_path, target_path in targets:
            text = source_path.read_text(encoding="utf-8")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(text, encoding="utf-8")
        return 0

    failed = []
    for source_path, target_path in targets:
        source_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
        target_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
        if source_text != target_text:
            failed.append((source_path, target_path))

    if failed:
        print("检测到 YAML DSL 编辑器 `schema` 漂移:")
        for source_path, target_path in failed:
            print("- {} != {}".format(str(target_path), str(source_path)))
        print("\n修复: 运行 `just gen-yaml-dsl-editor-schema`")
        return 1

    print("通过: YAML DSL 编辑器 `schema` 一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
