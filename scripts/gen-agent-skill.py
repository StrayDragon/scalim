#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
生成 `scalim-yaml-dsl` 技能的受控参考产物:

- 只生成 `artifacts/skills/scalim-yaml-dsl/references/*.gen.*`、
  `artifacts/skills/scalim-yaml-dsl/references/generated/` 与构建清单.
- 若存在 `artifacts/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md`,
  会在约定的“标记区块”内注入“升级批次索引”(来源: `docs/doc/yaml-dsl/upgrades/`).
- 语法目录来自 `src/scalim/dsl/by_yaml/schema/demand.gen.json`.
- CLI/LSP 参考来自 `src/scalim/cli/yaml_dsl.py`.
- 部分需求索引摘要来自 `openspec/specs/`.
- 唯一完整示例仅来自
  `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from scalim_misc import agent_skill_gen


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Scalim YAML DSL skill 的受控参考产物。")
    parser.add_argument("--output-root", help="技能输出根目录(默认: artifacts/skills)。")
    parser.add_argument("--validate", action="store_true", help="校验现有受控产物是否与重新生成结果一致。")
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
