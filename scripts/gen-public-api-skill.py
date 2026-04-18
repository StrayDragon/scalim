#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""生成 `scalim-public-api` 技能的受控参考产物.

约束:
- 只生成 `agentdev/skills/scalim-public-api/references/generated/**` 下的受控输出.
- MUST NOT 覆盖或重排 `agentdev/skills/scalim-public-api/SKILL.md`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from scalim_misc import public_api_skill_gen


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Scalim public API skill 的受控参考产物。")
    parser.add_argument("--output-root", help="技能输出根目录(默认: agentdev/skills)。")
    parser.add_argument("--validate", action="store_true", help="校验现有受控产物是否与重新生成结果一致。")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    output_root = Path(args.output_root) if args.output_root else repo_root / "agentdev" / "skills"
    skill_dir = output_root / public_api_skill_gen.SKILL_NAME

    if public_api_skill_gen.is_forbidden_output(skill_dir):
        raise SystemExit("拒绝写入用户技能目录.")

    try:
        if args.validate:
            ok = public_api_skill_gen.validate_skill(repo_root, output_root)
            return 0 if ok else 1
        public_api_skill_gen.build_skill(repo_root, output_root)
    except public_api_skill_gen.GenerationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
