from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    if not shutil.which("pnpm"):
        if os.environ.get("CI"):
            print("未找到 `pnpm`(CI 中 `YAML DSL` 编辑器 `dist` `schema` 检查需要它)", file=sys.stderr)
            return 1
        print("未找到 `pnpm`; 跳过 `YAML DSL` 编辑器 `dist` `schema` 检查", file=sys.stderr)
        return 0

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    dist_schema_dir = repo_root / "frontend" / "scalim-yaml-dsl-editor" / "dist" / "schema"

    expected = [
        ("demand.gen.json", schema_dir / "demand.gen.json"),
        ("workflow.gen.json", schema_dir / "workflow.gen.json"),
    ]

    if not dist_schema_dir.exists():
        if os.environ.get("CI"):
            print(
                "`YAML DSL` 编辑器 `dist` `schema` 目录缺失: " + str(dist_schema_dir),
                file=sys.stderr,
            )
            print("修复:", file=sys.stderr)
            print("  - 运行: `just frontend-yaml-dsl-editor-check`", file=sys.stderr)
            return 1
        print("`YAML DSL` 编辑器 `dist` `schema` 目录缺失; 跳过(未构建): " + str(dist_schema_dir), file=sys.stderr)
        return 0

    ok = True
    for file_name, canonical_path in expected:
        dist_path = dist_schema_dir / file_name
        if not dist_path.exists():
            print("`YAML DSL` 编辑器 `dist` `schema` 文件缺失: " + str(dist_path), file=sys.stderr)
            ok = False
            continue
        canonical_text = canonical_path.read_text(encoding="utf-8")
        dist_text = dist_path.read_text(encoding="utf-8")
        if canonical_text != dist_text:
            print("`YAML DSL` 编辑器 `dist` `schema` 漂移:", file=sys.stderr)
            print("  - " + str(dist_path) + " 与 " + str(canonical_path) + " 不一致", file=sys.stderr)
            ok = False

    if not ok:
        print("", file=sys.stderr)
        print("修复:", file=sys.stderr)
        print("  - 运行: `just gen-yaml-dsl-editor-schema`", file=sys.stderr)
        print("  - 重新运行: `just frontend-yaml-dsl-editor-check`", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
