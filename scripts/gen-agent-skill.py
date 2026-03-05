#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
生成 `Agent Skill` 数据的说明:

- 用 YAML 注释区域标记示例类型:
  `# region SCALIM-SKILL:<tag>[:<id>]` ... `# endregion`
  (标签: `minimal`、`advanced`、`relations`、`compute`、`relations-compute`、`example-full`).
- 扫描目录: `notebooks/marimo/examples/`; 区域内内容必须是合法的 YAML DSL.
- `schema` 元信息: 在 `src/scalim/dsl/by_yaml/schema_dsl/constants.py` 使用 `_schema_meta(md=..., examples=[...])`,
  会把 `markdownDescription`/`examples` 写入 `schema`(用于 `YAML LSP hover`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from scalim_misc import agent_skill_gen


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Scalim YAML DSL Agent Skill outputs.")
    parser.add_argument("--output-root", help="Output root directory for skills (default: artifacts/skills).")
    parser.add_argument("--validate", action="store_true", help="Validate existing outputs against generated content.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    output_root = Path(args.output_root) if args.output_root else repo_root / "artifacts" / "skills"
    skill_dir = output_root / agent_skill_gen.SKILL_NAME

    if agent_skill_gen.is_forbidden_output(skill_dir):
        raise SystemExit("拒绝写入用户技能目录.")

    try:
        if args.validate:
            ok = agent_skill_gen.validate_skill(repo_root, output_root)
            return 0 if ok else 1
        agent_skill_gen.build_skill(repo_root, output_root)
    except agent_skill_gen.GenerationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
